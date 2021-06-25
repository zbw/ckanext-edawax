import io
import re
import ast
import six
import hashlib
import logging
from ckan import model
from ckan.common import g, request, config, streaming_response
import ckan.lib.helpers as h
import ckan.plugins.toolkit as tk

import ckanext.edawax.notifications as n

import ckan.authz as authz
from ckan.authz import get_group_or_org_admin_ids
from ckanext.edawax.helpers import is_reviewer, in_review, hide_from_reviewer, is_private, is_published, is_robot, track_download, check_reviewer_update, _existing_user #, delete_cookies
from ckanext.edawax.update import update_maintainer_field, email_exists, invite_reviewer, add_user_to_journal

from ckanext.dara.helpers import check_journal_role

from functools import wraps

import flask
# Create Memver
from flask.views import MethodView
import ckan.lib.base as base
import ckan.logic as logic
import ckan.lib.navl.dictization_functions as dict_fns

NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError
check_access = logic.check_access
get_action = logic.get_action
tuplize_dict = logic.tuplize_dict
clean_dict = logic.clean_dict
parse_params = logic.parse_params

# for download all
import os
import io
import time
import zipfile
import requests
from ckanext.dara.helpers import _parse_authors
import ckan.lib.uploader as uploader
import flask

log = logging.getLogger(__name__)


"""
START Workflow
"""
def admin_req(func):
    @wraps(func)
    def check(*args, **kwargs):
        id = kwargs['id']
        pkg = tk.get_action('package_show')(None, {'id': id})
        if not check_journal_role(pkg, 'admin') and not h.check_access('sysadmin'):
            tk.abort(403, 'Unauthorized')
        return func(id)
    return check

def _context():
    return {'model': model, 'session': model.Session,
            'user': g.user or g.author, 'for_view': True,
            'auth_user_obj': g.userobj, 'save': 'save' in request.params}

def evaluate_reviewer(reviewer, reviewer_list, data_dict):
    """ Check if reviewer exists or not. Returns list of reviewer emails """
    if reviewer == '':
        return reviewer_list

    # must be an email address - check is handled in HTML with `pattern`
    # dont create a new user if the "reviewer" is already a reviewer
    existing_user = _existing_user(data_dict)
    new_reviewer = check_reviewer_update(data_dict)
    if '@' in reviewer:
        if new_reviewer and not existing_user:
            # create a new user with "reviewer" role for the dataset
            new_user = invite_reviewer(reviewer, data_dict['organization']['id'])
            update_maintainer_field(new_user['name'], reviewer, data_dict)
            # New reviewer, just send the invite
            reviewer_list = []
        else:
            # Reviewer has already been invited, a notification will be sent
            context = _context()
            context['ignore_auth'] = True
            users = tk.get_action('user_list')(context, {'email': reviewer})
            update_maintainer_field(users[0]['name'], reviewer, data_dict)
            reviewer_list.append(reviewer)

    else:
        h.flash_error("Reviewers must be given as email addresses.")
        log.debug(f"Reviewers aren't an email address: '{reviewer}'")
        return redirect(id)
    return reviewer_list


def review(id):
    """
    Sends review notification to all journal admins
    Check the maintainers: if one is an email address, invite that person
    to the JDA as a reviewer - need a new invitation that includes a link
    to the dataset for review.
    """
    # TODO: Look into allowing collaborators as reviewers?
    context = _context()
    pkg_dict = tk.get_action('package_show')(context, {'id': id})

    # Ensure a 'draft' isn't sent for review
    state = pkg_dict['state']
    if state == 'draft':
        data = {'id': pkg_dict['id'], u'state': u'active'}
        context['ignore_auth'] = True
        t = tk.get_action('package_patch')(context, data)
        pkg_dict['state'] = 'active'

    #delete_cookies(pkg_dict)

    try:
        tk.check_access('package_update', context, {'id': id})
    except tk.NotAuthorized:
        tk.abort(403, 'Unauthorized')

    # avoid multiple notifications (eg. when someone calls review directly)
    if pkg_dict.get('dara_edawax_review', 'false') == 'true':
        h.flash_error("Package has already been sent to review")
        return redirect(id)

    user_name = tk.c.userobj.fullname or tk.c.userobj.email
    admins = get_group_or_org_admin_ids(pkg_dict['owner_org'])
    addresses = list(map(lambda admin_id: model.User.get(admin_id).email, admins))

    data_dict = pkg_dict
    reviewer = data_dict.get("maintainer", None)
    reviewer_emails = []
    flash_message = None
    context['keep_email'] = True

    try:
        # If there is a reviewer
        if reviewer != '':
            if reviewer is not None:
                reviewer = reviewer.split('/')[0]
                # reviewer is an email address
                try:
                    reviewer_list = evaluate_reviewer(reviewer, reviewer_emails, data_dict)
                    flash_message = ('Notification sent to Reviewers.', 'success')
                    log_msg = '\nNotifications sent to:\nReviewers:{}\nRest: {}'
                    log.debug(log_msg.format(reviewer_emails, addresses))
                except Exception as e:
                    flash_message = ('ERROR: Mail could not be sent. Please try again later or contact the site admin.', 'error')
                    log.debug('Failed to send notifications')
                    log.error(f'ERROR: {e}')
    except Exception as e:
        log.error(f"Error with reviewer notifications: {e.message}-{e.args}")
        log.error(reviewer_emails)

    # the author is sending the dataset to the editor, there are no reviewers
    # Or it is coming back from being reworked by the author
    if flash_message is None \
        and (reviewer_emails == []) \
            or data_dict['dara_edawax_review'] in ['reauthor', 'false']:
        note = n.review(addresses, user_name, id, reviewer_emails)
    elif len(reviewer_emails) > 0:
        # There is a reviewer, notify them
        note = n.review(None, user_name, id, reviewer_emails)
    elif flash_message and (reviewer_emails == []):
        # if there is a flash message and no reviewers, an invitation was sent
        note = True
    else:
        note = False

    if note:
        pkg_dict = update_review_status(pkg_dict)
        tk.get_action('package_update')(context, pkg_dict)
        if flash_message is None:
            flash_message = ('Notification sent to Editor.', 'success')
    else:
        flash_message = ('Error: Mail could not be sent. Please try again later or contact the site admin.', 'error')

    if flash_message[1] == 'success':
        h.flash_success(flash_message[0])
    else:
        h.flash_error(flash_message[0])

    return redirect(id)


def update_review_status(pkg_dict, action=None):
    """
        Update the status of "dara_edawax_review"
        Status:
            - false = beginning of review phase
            - editor = editor has for review
            - reviewers = reviewers have for review
            - reviewed = review is finished
            - reauthor = sent back to author
            - back = back to editor from reviewers
        false -> editor
        editor -> reviewers || reauthor
        reviewers -> back
        back -> reviewed
    """
    current_state = pkg_dict['dara_edawax_review']

    if current_state == 'false':
        pkg_dict['dara_edawax_review'] = 'editor'

    if current_state in ['editor', 'back']:
        pkg_dict['dara_edawax_review'] = 'reviewers'

    if current_state == 'reauthor':
        pkg_dict['dara_edawax_review'] = 'editor'

    # fix for typo
    if current_state == 'reviewer':
        pkg_dict['dara_edawax_review'] = 'reviewers'

    return pkg_dict


@admin_req
def publish(id):
    """
    publish dataset
    """
    context = _context()
    pkg_dict = tk.get_action('package_show')(context, {'id': id})

    # validate the DOI, if any
    try:
        doi = pkg_dict['dara_Publication_PID']
        type_ = pkg_dict['dara_Publication_PIDType']
    except KeyError:
        doi = ''
        type_ = ''

    if type_ == 'DOI':
        pattern = re.compile('^10.\d{4,9}/[-._;()/:a-zA-Z0-9]+$')
        match = pattern.match(doi)
        if match is None:
            h.flash_error('DOI is invalid. Format should be: 10.xxxx/xxxx. Please update the DOI before trying again to publish this resource. <a href="#doi" style="color: blue;">Jump to field.</a>', True)
            errors = {'dara_Publication_PID': ['DOI is invalid. Format should be: 10.xxxx/xxxx']}

            return h.redirect_to('dataset.edit', id=id)

    pkg_dict.update({'private': False, 'dara_edawax_review': 'reviewed'})
    pkg = context.get('package')
    tk.get_action('package_update')(context, pkg_dict)
    h.flash_success('Dataset published')
    author_notify(id)
    return redirect(id)



@admin_req
def retract(id):
    """
    set dataset private and back to review state
    """
    context = _context()
    pkg_dict = tk.get_action('package_show')(context, {'id': id})

    if pkg_dict.get('dara_DOI_Test', False) and not h.check_access('sysadmin'):
        h.flash_error("ERROR: DOI (Test) already assigned, dataset can't be retracted")
        return redirect(id)

    if pkg_dict.get('dara_DOI', False):
        h.flash_error("ERROR: DOI already assigned, dataset can't be retracted")
        return redirect(id)

    pkg_dict.update({'private': True, 'dara_edawax_review': 'false'})
    tk.get_action('package_update')(context, pkg_dict)

    # notify author about the retraction
    author_notify(id)
    h.flash_success('Dataset retracted')
    return redirect(id)


@admin_req
def reauthor(id):
    """
    Reset dataset to private and leave review state.
    Should also send email to author
    """
    context = _context()
    msg = request.form.get('msg', '')
    pkg_dict = tk.get_action('package_show')(context, {'id': id})
    #delete_cookies(pkg_dict)
    creator_mail = model.User.get(pkg_dict['creator_user_id']).email
    admin_mail = model.User.get(g.user).email
    #note = n.reauthor(id, creator_mail, admin_mail, msg, context)
    note = n.notify('reauthor', id, creator_mail, msg, context)

    if note:
        pkg_dict.update({'private': True,
                            'dara_edawax_review': 'reauthor'})
        tk.get_action('package_update')(context, pkg_dict)
        h.flash_success('Notification sent. Dataset can now be re-edited by author')
    else:
        h.flash_error('ERROR: Mail could not be sent. Please try again later or contact the site admin.')
    return redirect(id)


def editor_notify(id):
    """
    Send from reviewer back to editor
    """
    context = _context()
    msg = request.form.get('msg', '')
    pkg_dict = tk.get_action('package_show')(context, {'id': id})
    creator_mail = model.User.get(pkg_dict['creator_user_id']).email
    note = n.notify('editor', id, creator_mail, msg, context)

    if note:
        pkg_dict.update({'private': True, 'dara_edawax_review': 'back'})
        tk.get_action('package_update')(context, pkg_dict)
        h.flash_success('Notification sent. Journal Editor will be notified.')
    else:
        h.flash_error('ERROR: Mail could not be sent. Please try again later or contact the site admin.')
    return redirect(id)


def author_notify(id):
    """ Send mail from the system to the author """
    context = _context()
    msg = request.form.get('msg', '')
    pkg_dict = tk.get_action('package_show')(context, {'id': id})

    if pkg_dict['dara_edawax_review'] == 'reviewed':
        status = 'published'
    else:
        status = 'retracted'
    author_email = model.User.get(pkg_dict['creator_user_id']).email
    note = n.notify('author', id, author_email, msg, context, status)


def create_citataion_text(id):
    """ Create a plain text file with a citation. Will be included in
        the "download_all" zip file
        """
    context = _context()
    data = tk.get_action('package_show')(context, {'id': id})

    citation = u'{authors} ({year}): {dataset}. Version: {version}. {journal}. Dataset. {address}'

    journal_map = {
                    'GER': 'German Economic Review',
                    'AEQ': 'Applied Economics Quarterly',
                    'IREE': 'International Journal for Re-Views in Empirical Economics',
                    'VSWG': 'Vierteljahrschrift für Sozial- und Wirtschaftsgeschichte'
                    }

    if is_reviewer(data):
        authors = "********"
    else:
        authors = _parse_authors(data['dara_authors'])

    year = data.get('dara_PublicationDate', '')
    dataset_name = data.get('title', '')
    dataset_version = data.get('dara_currentVersion', '')

    temp_title = data['organization']['title']
    if temp_title in journal_map.keys():
        journal_title = journal_map[temp_title]
    else:
        journal_title = temp_title

    if data['dara_DOI'] != '':
        address = f"https://doi.org/{data['dara_DOI']}"
    else:
        site_url = config.get('ckan.site_url')
        name = data['name']
        address = f'{site_url}/dataset/{name}'

    return citation.format(authors=authors,
                            year=year,
                            dataset=dataset_name,
                            version=dataset_version,
                            journal=journal_title,
                            address=address)


def download_all(id):
    referrer = request.referrer
    if referrer:
        data = {}
        context = _context()
        pkg_dict = tk.get_action('package_show')(context, {'id': id})
        zip_sub_dir = 'resources'
        title = pkg_dict['title'].replace(' ', '_').replace(',', '_')
        time_ = time.time()
        zip_name = f"{title}_resouces_{time_}.zip"
        resources = pkg_dict['resources']
        for resource in resources:
            rsc = tk.get_action('resource_show')(context, {'id': resource['id']})
            if rsc.get('url_type') == 'upload' and not is_robot(request.user_agent):
                agent = request.user_agent
                remote_addr = request.remote_addr
                languages = getattr(request, 'accept_languages', '')
                encodings = getattr(request, 'accept_encodings', '')
                user_key = f'{agent}{remote_addr}{languages}{encodings}'
                key = hashlib.md5(six.ensure_binary(user_key)).hexdigest()
                url = resource['url']
                filename = os.path.basename(url)
                try:
                    upload = uploader.get_resource_uploader(rsc)
                    filepath = upload.get_path(rsc[u'id'])
                    data[filename] = filepath
                    if is_published(url):
                        added, msg = track_download(url, filename, key)
                    else:
                        added = False
                        msg = 'Not published'
                    if added:
                        log.info(f'Tracked: {url}')
                    else:
                        log.error(f'Didn\'t track: {url} - {msg}')
                except Exception as e:
                    print(f'Error: {e}')

        data['citation.txt'] = create_citataion_text(id)
        if len(data) > 0:
            memory_file = io.BytesIO()
            with zipfile.ZipFile(memory_file, 'w') as zf:
                for item, content in data.items():
                    zip_path = os.path.join(zip_sub_dir, item)
                    try:
                        zf.write(content, zip_path)
                    except Exception:
                        zf.writestr(zip_path, content)
            memory_file.seek(0)
            return flask.send_file(memory_file, attachment_filename=zip_name, as_attachment=True)
    # if there's nothing to download but someone gets to the download page
    # /download_all, return them to the landing page
    h.flash_error('Nothing to download.')
    return redirect(id)

"""
END Workflow
"""


"""
START INFO Views
"""
TEMPLATE = "info_index.html"

def index():
    return tk.render(TEMPLATE, extra_vars={'page': 'index'})

def md_page(id):
    plist = tk.request.path.rsplit('/', 1)
    return tk.render(TEMPLATE, extra_vars={'page': plist[-1]})


"""
END INFO Views
"""

def context():
    return {'model': model, 'session': model.Session,
           'user': g.user or g.author, 'for_view': True,
           'auth_user_obj': g.userobj, 'ignore_auth': True}

def redirect(id):
    return h.redirect_to(u'dataset.read', id=id)

def create_citation(type, id):
    check_access('package_show',
                         {'model': model, 'session': model.Session,
                          'user': g.user or g.author, 'for_view': True,
                          'auth_user_obj': g.userobj},
                          {'id': id})
    if type == 'ris':
        return create_ris_record(id)
    elif type == 'bibtex':
        return create_bibtex_record(id)
        return r
    else:
        h.flash_error(f"Couldn't build {type} citation.")
        return redirect(id)

def parse_ris_authors(authors):
    out = ''
    line = 'AU  - {last}, {first}\n'
    authors = ast.literal_eval(authors.replace("null", "None"))
    for author in authors:
        out += line.format(last=author['lastname'], first=author['firstname'])
    return out


def parse_bibtex_authors(authors):
    temp_str = ''
    temp_list = []
    authors = ast.literal_eval(authors.replace("null", "None"))
    for author in authors:
        temp_list.append(f"{author['lastname']}, {author['firstname']}")
    if len(temp_list) > 1:
        return " and ".join(temp_list)
    else:
        return temp_list[0]



def parse_ris_doi(doi):
    if doi != '':
        return f'DO  - doi:{doi}\n'
    return ''

def create_ris_record(id):
    pkg_dict = tk.get_action('package_show')(context(), {'id': id})
    title = pkg_dict['title'].encode('utf-8')
    if is_reviewer(pkg_dict):
        authors = "AU  - ********\n"
    else:
        try:
            authors = parse_ris_authors(pkg_dict['dara_authors'])
        except KeyError:
            if 'dara_authors' not in pkg_dict.keys():
                authors = pkg_dict['author'] or ''
            authors = ''
    date = pkg_dict.get('dara_PublicationDate', '????')
    try:
        journal = pkg_dict['organization']['title']
    except TypeError as e:
        journal = ''
    site_url = config.get('ckan.site_url')
    title = pkg_dict['name']
    url = f'{site_url}/dataset/{title}'
    version = pkg_dict.get('dara_currentVersion', '1')

    if 'dara_DOI' in pkg_dict.keys():
        doi = parse_ris_doi(pkg_dict['dara_DOI'])
    else:
        doi = ''

    if pkg_dict['notes'] != '':
        value = pkg_dict['notes'].replace('\n', ' ').replace('\r', ' ')
        abstract = f'AB  - {value}\n'
    else:
        abstract = ''

    if 'dara_jels' in pkg_dict.keys():
        jels = ''
        for jel in pkg_dict['dara_jels']:
            jels += f'KW  - {jel}\n'
    else:
        jels = ''

    contents = f"TY  - DATA\nT1  - {title}\n{authors}{doi}{abstract}{jels}ET  - {version}\nPY  - {date}\nPB  - ZBW - Leibniz Informationszentrum Wirtschaft\nUR  - {url}\nER  - \n"

    file = io.BytesIO()
    file.write(str.encode(contents))
    file.seek(0)

    return flask.send_file(file, mimetype="application/download",
                           attachment_filename=f"{pkg_dict['name']}_citation.ris",
                           as_attachment=True)



def create_bibtex_record(id):
    pkg_dict = tk.get_action('package_show')(context(), {'id': id})
    title = pkg_dict['title'].encode('utf-8')
    if is_reviewer(pkg_dict):
        authors = "********"
    else:
        try:
            authors = parse_bibtex_authors(pkg_dict['dara_authors'])
        except KeyError:
            if 'dara_authors' not in pkg_dict.keys():
                authors = pkg_dict['author'] or ''
            authors = ''
    date = pkg_dict.get('dara_PublicationDate', '????')
    try:
        journal = pkg_dict['organization']['title'].encode('utf-8')
    except TypeError as e:
        journal = ''
    site_url = config.get('ckan.site_url')
    title = pkg_dict['name']
    url = f'{site_url}/dataset/{title}'
    version = pkg_dict.get('dara_currentVersion', '1')
    if 'dara_DOI' in pkg_dict.keys() and pkg_dict['dara_DOI'] != '':
        temp_doi = pkg_dict['dara_DOI']
        identifier = f"{temp_doi.split('/')[1]}"
    else:
        identifier = f"{pkg_dict['name'][:10]}/{date}"

    if 'dara_DOI' in pkg_dict.keys() and pkg_dict['dara_DOI'] != '':
        doi = f",\ndoi = \"{pkg_dict['dara_DOI']}\""
    else:
        doi = ''

    if 'dara_jels' in pkg_dict.keys():
        jels = ',\nkeywords = {'
        for x, jel in enumerate(pkg_dict['dara_jels']):
            if x < len(pkg_dict['dara_jels']) - 1:
                jels += f'{jel},'
            else:
                jels += f'{jel}}}'
    else:
        jels = ''

    contents = f'@data{{{identifier},\nauthor = {{{authors}}},\npublisher = {{ZBW - Leibniz Informationszentrum Wirtschaft}},\ntitle = {{{title}}},\nyear = {{{date}}},\nversion = {{{version}}},\nurl = {{{url}}}{jels}{doi} \n}}'

    file = io.BytesIO()
    file.write(str.encode(contents))
    file.seek(0)

    return flask.send_file(file, mimetype="text/plain",
                            attachment_filename=f"{pkg_dict['name']}_citation.bib",
                            as_attachment=True)


"""
    Copied from /views/groups.py because I need to make adjustments for
    how errors are handled. When an email belongs to an existing user
    there was a server error being thrown.
"""
def set_org(is_organization):
    global is_org
    is_org = is_organization

def _check_access(action_name, *args, **kw):
    u''' select the correct group/org check_access '''
    return check_access(_replace_group_org(action_name), *args, **kw)

def _action(action_name):
    u''' select the correct group/org action '''
    return get_action(_replace_group_org(action_name))

def _replace_group_org(string):
    u''' substitute organization for group if this is an org'''
    if is_org:
        return re.sub(u'^group', u'organization', string)
    return string

class MembersGroupView(MethodView):
    u'''New members group view'''

    def _prepare(self, id=None):
        context = {
            u'model': model,
            u'session': model.Session,
            u'user': g.user
        }
        try:
            _check_access(u'group_member_create', context, {u'id': id})
        except NotAuthorized:
            base.abort(403,
                       _(u'Unauthorized to create group %s members') % u'')

        return context

    def post(self, group_type, is_organization, id=None):
        set_org(is_organization)
        context = self._prepare(id)
        data_dict = clean_dict(
            dict_fns.unflatten(tuplize_dict(parse_params(request.form))))
        data_dict['id'] = id

        email = data_dict.get(u'email')

        if email:
            user_data_dict = {
                u'email': email,
                u'group_id': data_dict['id'],
                u'role': data_dict['role']
            }
            del data_dict['email']
            user_dict = _action(u'user_invite')(context, user_data_dict)
            data_dict['username'] = user_dict['name']

        if data_dict['username']:
            try:
                group_dict = _action(u'group_member_create')(context, data_dict)
            except NotAuthorized:
                base.abort(403, _(u'Unauthorized to add member to group %s') % u'')
            except NotFound:
                base.abort(404, _(u'Group not found'))
            except ValidationError as e:
                h.flash_error(e.error_summary)
                return h.redirect_to(u'journals.member_new', id=id)
        else:
            h.flash_error(f"The email address '{email}' belongs to a registered user.")
            return h.redirect_to(u'journals.member_new', id=id)

        # TODO: Remove
        g.group_dict = group_dict

        return h.redirect_to(u'{}.members'.format(group_type), id=id)

    def get(self, group_type, is_organization, id=None):
        extra_vars = {}
        set_org(is_organization)
        context = self._prepare(id)
        user = request.params.get(u'user')
        data_dict = {u'id': id}
        data_dict['include_datasets'] = False
        group_dict = _action(u'group_show')(context, data_dict)
        roles = _action(u'member_roles_list')(context, {
            u'group_type': group_type
        })
        user_dict = {}
        if user:
            user_dict = get_action(u'user_show')(context, {u'id': user})
            user_role =\
                authz.users_role_for_group_or_org(id, user) or u'member'
            # TODO: Remove
            g.user_dict = user_dict
            extra_vars["user_dict"] = user_dict
        else:
            user_role = u'member'


        # TODO: Remove
        g.group_dict = group_dict
        g.roles = roles
        g.user_role = user_role

        extra_vars.update({
            u"group_dict": group_dict,
            u"roles": roles,
            u"user_role": user_role,
            u"group_type": group_type,
            u"user_dict": user_dict
        })
        return base.render(_replace_group_org(u'group/member_new.html'),
                           extra_vars)
