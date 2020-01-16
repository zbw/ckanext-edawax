# -*- coding: utf-8 -*-
# Hendrik Bunke
# ZBW - Leibniz Information Centre for Economics
import re
from ckan.controllers.package import PackageController
import ckan.plugins.toolkit as tk
from ckan.common import c, request, _, response
from ckan import model
import ckan.lib.helpers as h
import logging
from ckan.authz import get_group_or_org_admin_ids
from ckanext.dara.helpers import check_journal_role
from functools import wraps
import notifications as n
from ckanext.edawax.helpers import is_private, is_robot
from pylons import config

# for download all
import os
import time
import zipfile
import requests
import StringIO
from ckanext.dara.helpers import _parse_authors
from ckanext.edawax.helpers import is_reviewer, in_review, delete_cookies
from ckanext.edawax.update import update_maintainer_field, email_exists, invite_reviewer, check_reviewer, add_user_to_journal

import ckan.lib.base as base


import ast
from webob import Response, Request

log = logging.getLogger(__name__)


def admin_req(func):
    @wraps(func)
    def check(*args, **kwargs):
        id = kwargs['id']
        controller = args[0]
        pkg = tk.get_action('package_show')(None, {'id': id})
        if not check_journal_role(pkg, 'admin') and not h.check_access('sysadmin'):
            tk.abort(403, 'Unauthorized')
        return func(controller, id)
    return check


class WorkflowController(PackageController):
    """
    """

    def _context(self):
        return {'model': model, 'session': model.Session,
                'user': c.user or c.author, 'for_view': True,
                'auth_user_obj': c.userobj, 'save': 'save' in request.params}


    def evaluate_reviewer(self, reviewer, reviewer_list):
        """ Check if reveiwer exists or not. Returns list of reviewer emails """
        context = self._context()
        context['keep_email'] = True
        if reviewer is not None and '@' in reviewer:
            log.debug('Reviewer is an email address')
            data_dict, old = check_reviewer(data_dict,reviewer,"maintainer")
            if old:
                log.debug('Reviewer already exists')
                reviewer_list.append(reviewer)
            else:
                log.debug('Reviewer is new')
                reviewer_list.append(None)
            reviewer = data_dict['name']
            # if the reviewer is new
            # don't notify them about the review, only send an
            # invitation that says they can review
        else:
            log.debug('Reviewer is a user name')
            # otherwise just notify them that they can review
            try:
                print('#############')
                print(reviewer)
                reviewer_list.append(tk.get_action('user_show')(context, {'id': reviewer})['email'])
                print(lst)
                add_user_to_journal(c.pkg_dict, c.pkg_dict['organization']['id'], "maintainer", "reviewer")
            except Exception as e:
                print('Error getting email for reveiwer: {}\n{}'.format(reviewer, e))
                reviewer_list.append(None)
        return reviewer_list


    def review(self, id):
        """
        sends review notification to all journal admins

        Check the maintainers: if one is an email address, invite that person
        to the JDA as a reviewer - need a new invitation that includes a link
        to the dataset for review.
        """
        log.debug('Sending to reviewers')
        context = self._context()
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})

        delete_cookies(c.pkg_dict)

        try:
            tk.check_access('package_update', context, {'id': id})
        except tk.NotAuthorized:
            tk.abort(403, 'Unauthorized')

        # avoid multiple notifications (eg. when someone calls review directly)
        if c.pkg_dict.get('dara_edawax_review', 'false') == 'true':
            h.flash_error("Package has already been sent to review")
            redirect(id)

        user_name = tk.c.userobj.fullname or tk.c.userobj.email
        admins = get_group_or_org_admin_ids(c.pkg_dict['owner_org'])
        addresses = map(lambda admin_id: model.User.get(admin_id).email,admins)

        data_dict = c.pkg_dict
        reviewer_1 = data_dict.get("maintainer", None)
        reviewer_2 = data_dict.get("maintainer_email", None)
        reviewer_emails = []

        log.debug("context: {}".format(context))
        context['keep_email'] = True

        log.debug("Reviewer 1: {}".format(reviewer_1))
        log.debug("Reviewer 2: {}".format(reviewer_2))

        try:
            if (reviewer_1 != '' or reviewer_2 != ''):
                if reviewer_1 is not None and reviewer_2 is not None:
                    # reviewer is an email address
                    reviewer_emails = self.evaluate_reviewer(reviewer_1, reviewer_emails)
                    reviewer_emails = self.evaluate_reviewer(reviewer_2, reviewer_emails)
                else:
                    log.debug('Reviewers are empty')
                    reviewer_emails = [reviewer_1, reviewer_2]
            else:
                log.debug('Reviewers are empty')
                reviewer_emails = [None, None]
        except Exception as e:
            log.debug("Error with reviewer notifcations: {}".format(e))

        # check that there are reviewers
        flash_message = ""
        if reviewer_emails[0] is None \
            and reviewer_emails[1] is None \
                and c.pkg_dict['dara_edawax_review'] != 'false':
            if c.pkg_dict['dara_edawax_review'] == 'editor':
                flash_message = ('This submission has no reviewers.', 'error')
                redirect(id)

        log.debug('Sending Notifications to: {}'.format(reviewer_emails))
        note = n.review(addresses, user_name, id, reviewer_emails)
        log.debug('Notifications sent to : {}'.format(reviewer_emails))

        if note:
            c.pkg_dict = self.update_review_status(c.pkg_dict)
            tk.get_action('package_update')(context, c.pkg_dict)
            if flash_message == "":
                flash_message = ('Notification sent to Reviewers.', 'success')
        else:
            flash_message = ('ERROR: Mail could not be sent. Please try again later or contact the site admin.', 'error')

        if flash_message[1] == 'success':
            h.flash_success(flash_message[0])
        else:
            h.flash_error(flash_message[0])

        redirect(id)


    def update_review_status(self, pkg_dict, action=None):
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

        return pkg_dict


    @admin_req
    def publish(self, id):
        """
        publish dataset
        """
        context = self._context()
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})

        # validate the DOI, if any
        try:
            doi = c.pkg_dict['dara_Publication_PID']
            type_ = c.pkg_dict['dara_Publication_PIDType']
        except KeyError:
            doi = ''
            type_ = ''

        if type_ == 'DOI':
            pattern = re.compile('^10.\d{4,9}/[-._;()/:a-zA-Z0-9]+$')
            match = pattern.match(doi)
            if match is None:
                h.flash_error('DOI is invalid. Format should be: 10.xxxx/xxxx. Please update the DOI before trying again to publish this resource. <a href="#doi" style="color: blue;">Jump to field.</a>', True)
                errors = {'dara_Publication_PID': ['DOI is invalid. Format should be: 10.xxxx/xxxx']}

                tk.redirect_to(controller='package', action='edit', id=id)

        c.pkg_dict.update({'private': False, 'dara_edawax_review': 'reviewed'})
        c.pkg = context.get('package')
        tk.get_action('package_update')(context, c.pkg_dict)
        h.flash_success('Dataset published')

        # notify the author
        self.author_notify(id)

        redirect(id)


    @admin_req
    def retract(self, id):
        """
        set dataset private and back to review state
        """
        context = self._context()
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})

        if c.pkg_dict.get('dara_DOI_Test', False) and not h.check_access('sysadmin'):
            h.flash_error("ERROR: DOI (Test) already assigned, dataset can't be retracted")
            redirect(id)

        if c.pkg_dict.get('dara_DOI', False):
            h.flash_error("ERROR: DOI already assigned, dataset can't be retracted")
            redirect(id)

        c.pkg_dict.update({'private': True, 'dara_edawax_review': 'false'})
        tk.get_action('package_update')(context, c.pkg_dict)

        # notify author about the retraction
        self.author_notify(id)
        h.flash_success('Dataset retracted')
        redirect(id)


    @admin_req
    def reauthor(self, id):
        """reset dataset to private and leave review state.
        Should also send email to author
        """
        context = self._context()
        msg = tk.request.params.get('msg', '')
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        delete_cookies(c.pkg_dict)
        creator_mail = model.User.get(c.pkg_dict['creator_user_id']).email
        admin_mail = model.User.get(c.user).email
        #note = n.reauthor(id, creator_mail, admin_mail, msg, context)
        note = n.notify('reauthor', id, creator_mail, msg, context)

        if note:
            c.pkg_dict.update({'private': True,
                               'dara_edawax_review': 'reauthor'})
            tk.get_action('package_update')(context, c.pkg_dict)
            h.flash_success('Notification sent. Dataset can now be re-edited by author')
        else:
            h.flash_error('ERROR: Mail could not be sent. Please try again later or contact the site admin.')
        redirect(id)


    def editor_notify(self, id):
        """ Send from reviewer back to editor """
        context = self._context()
        msg = tk.request.params.get('msg', '')
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        creator_mail = model.User.get(c.pkg_dict['creator_user_id']).email
        note = n.notify('editor', id, creator_mail, msg, context)

        if note:
            c.pkg_dict.update({'private': True, 'dara_edawax_review': 'back'})
            tk.get_action('package_update')(context, c.pkg_dict)
            h.flash_success('Notification sent. Journal editor will be notified.')
        else:
            h.flash_error('ERROR: Mail could not be sent. Please try again later or contact the site admin.')
        redirect(id)


    def author_notify(self, id):
        """ Send mail from the system to the author """
        context = self._context()
        msg = tk.request.params.get('msg', '')
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})

        if c.pkg_dict['dara_edawax_review'] == 'reviewed':
            status = 'published'
        else:
            status = 'retracted'
        author_email = model.User.get(c.pkg_dict['creator_user_id']).email
        note = n.notify('author', id, author_email, msg, context, status)


    def create_citataion_text(self, id):
        """ Create a plain text file with a citation. Will be included in
            the "download_all" zip file
         """
        context = self._context()
        data = tk.get_action('package_show')(context, {'id': id})
        citation = '{authors} ({year}): {dataset}. Version: {version}. {journal}. Dataset. {address}'

        journal_map = {
                        'GER': 'German Economic Review',
                        'AEQ': 'Applied Economics Quarterly',
                        'IREE': 'International Journal for Re-Views in Empirical Economics',
                        'VSWG': 'Vierteljahrschrift für Sozial- und Wirtschaftsgeschichte'
                      }

        authors = _parse_authors(data['dara_authors'])
        year = data.get('dara_PublicationDate', '')
        dataset_name = data.get('title', '').encode('utf-8')
        dataset_version = data.get('dara_currentVersion', '')

        temp_title = data['organization']['title']
        if temp_title in journal_map.keys():
            journal_title = journal_map[temp_title]
        else:
            journal_title = temp_title

        if data['dara_DOI'] != '':
            address = 'https://doi.org/{}'.format(data['dara_DOI'])
        else:
            address = '{}/dataset/{}'.format(config.get('ckan.site_url'), data['name'])

        return citation.format(authors=authors,
                               year=year,
                               dataset=dataset_name,
                               version=dataset_version,
                               journal=journal_title,
                               address=address)


    def download_all(self, id):
        data = {}
        context = self._context()
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        zip_sub_dir = 'resources'
        zip_name = u"{}_resouces_{}.zip".format(c.pkg_dict['title'].replace(' ', '_').replace(',', '_'), time.time())

        resources = c.pkg_dict['resources']
        for resource in resources:
            rsc = tk.get_action('resource_show')(context, {'id': resource['id']})
            if rsc.get('url_type') == 'upload' and not is_robot(request.user_agent):
                url = resource['url']
                filename = os.path.basename(url)
                # custom user agent header so that downloads from here count
                headers = {
                    'User-Agent': 'Ckan-Download-All Agent 1.0',
                    'From': 'journaldata@zbw.eu'
                }
                try:
                    ca_file = config.get('ckan.cert_path')
                    r = requests.get(url, stream=True, headers=headers,
                            verify=ca_file)
                except Exception:
                    r = requests.get(url, stream=True, headers=headers)
                if r.status_code != 200:
                    h.flash_error('Failed to download files.')
                    redirect(id)
                else:
                    data[filename] = r

        data['citation.txt'] = self.create_citataion_text(id)
        if len(data) > 0:
            s = StringIO.StringIO()
            zf = zipfile.ZipFile(s, "w")
            for item, content in data.items():
                zip_path = os.path.join(zip_sub_dir, item)
                try:
                    zf.writestr(zip_path, content.content)
                except Exception as e:
                    # adding the citation file
                    zf.writestr(zip_path, content)
            zf.close()
            response.headers.update({"Content-Disposition": "attachment;filename={}".format(zip_name.encode('utf8'))})
            response.content_type = "application/zip"
            return s.getvalue()
        # if there's nothing to download but someone gets to the download page
        # /download_all, return them to the landing page
        h.flash_error('Nothing to download.')
        redirect(id)


def redirect(id):
    tk.redirect_to(controller='package', action='read', id=id)

context = {'model': model, 'session': model.Session,
           'user': c.user or c.author, 'for_view': True,
           'auth_user_obj': c.userobj, 'ignore_auth': True}


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
        temp_list.append('{}, {}'.format(author['lastname'], author['firstname']))
    if len(temp_list) > 1:
        return " and ".join(temp_list)
    else:
        return temp_list[0]


def parse_ris_doi(doi):
    if doi != '':
        return 'DO  - doi:{}\n'.format(doi)
    return ''

def create_ris_record(id):
    contents = "TY  - DATA\nT1  - {title}\n{authors}{doi}{abstract}{jels}ET  - {version}\nPY  - {date}\nPB  - ZBW - Leibniz Informationszentrum Wirtschaft\nUR  - {url}\nER  - \n"
    pkg_dict = tk.get_action('package_show')(context, {'id': id})
    title = pkg_dict['title'].encode('utf-8')
    try:
        authors = parse_ris_authors(pkg_dict['dara_authors'])
    except KeyError:
        if 'dara_authors' not in pkg_dict.keys():
            authors = pkg_dict['author'] or ''
        authors = ''
    date = pkg_dict['dara_PublicationDate']
    try:
        journal = pkg_dict['organization']['title']
    except TypeError as e:
        journal = ''
    url = '{}/dataset/{}'.format(config.get('ckan.site_url'), pkg_dict['name'])
    version = pkg_dict['dara_currentVersion']
    if 'dara_DOI' in pkg_dict.keys():
        doi = parse_ris_doi(pkg_dict['dara_DOI'])
    else:
        doi = ''

    if pkg_dict['notes'] != '':
        abstract = 'AB  - {}\n'.format(pkg_dict['notes'].encode('utf-8').replace('\n', ' ').replace('\r', ' '))
    else:
        abstract = ''

    if 'dara_jels' in pkg_dict.keys():
        jels = ''
        for jel in pkg_dict['dara_jels']:
            jels += 'KW  - {}\n'.format(jel)
    else:
        jels = ''

    contents = contents.format(title=title,
                               authors=authors,
                               doi=doi,
                               date=date,
                               journal=journal,
                               url=url,
                               version=version,
                               abstract=abstract,
                               jels=jels)

    s = StringIO.StringIO()
    s.write(contents)

    response.headers.update({"Content-Disposition": "attachment;filename={}_citation.ris".format(pkg_dict['name'])})
    response.content_type = "application/download"
    res = Response(content_type = "application/download")
    response.body = contents

    return res


def create_bibtex_record(id):
    pkg_dict = tk.get_action('package_show')(context, {'id': id})
    title = pkg_dict['title'].encode('utf-8')
    try:
        authors = parse_bibtex_authors(pkg_dict['dara_authors'])
    except KeyError:
        if 'dara_authors' not in pkg_dict.keys():
            authors = pkg_dict['author'] or ''
        authors = ''
    date = pkg_dict['dara_PublicationDate']
    try:
        journal = pkg_dict['organization']['title'].encode('utf-8')
    except TypeError as e:
        journal = ''
    url = '{}/dataset/{}'.format(config.get('ckan.site_url'), pkg_dict['name'])
    version = pkg_dict['dara_currentVersion']
    if 'dara_DOI' in pkg_dict.keys() and pkg_dict['dara_DOI'] != '':
        temp_doi = pkg_dict['dara_DOI']
        identifier = '{}'.format(temp_doi.split('/')[1])
    else:
        identifier = '{}/{}'.format(pkg_dict['name'][:10], date)

    if 'dara_DOI' in pkg_dict.keys() and pkg_dict['dara_DOI'] != '':
        doi = ',\ndoi = "{}"'.format(pkg_dict['dara_DOI'])
    else:
        doi = ''

    if 'dara_jels' in pkg_dict.keys():
        jels = ',\nkeywords = {'
        for x, jel in enumerate(pkg_dict['dara_jels']):
            if x < len(pkg_dict['dara_jels']) - 1:
                jels += '{},'.format(jel)
            else:
                jels += '{}}}'.format(jel)
    else:
        jels = ''

    contents = '@data{{{identifier},\nauthor = {{{authors}}},\npublisher = {{ZBW - Leibniz Informationszentrum Wirtschaft}},\ntitle = {{{title}}},\nyear = {{{date}}},\nversion = {{{version}}},\nurl = {{{url}}}{jels}{doi} \n}}'

    contents = contents.format(identifier=identifier, authors=authors, title=title,date=date,version=version,url=url,doi=doi,jels=jels)

    s = StringIO.StringIO()
    s.write(contents)

    response.headers.update({"Content-Disposition": "attachment;filename={}_citation.bib".format(pkg_dict['name'])})
    response.content_type = "text/plain"
    res = Response(content_type = "application/download")
    response.body = contents

    return res



class InfoController(tk.BaseController):

    TEMPLATE = "info_index.html"

    def index(self):
        return tk.render(self.TEMPLATE, extra_vars={'page': 'index'})

    def md_page(self):
        plist = tk.request.path.rsplit('/', 1)
        return tk.render(self.TEMPLATE, extra_vars={'page': plist[-1]})


    def create_citation(self, type, id):
        if type == 'ris':
            create_ris_record(id)
        elif type == 'bibtex':
            create_bibtex_record(id)
        else:
            h.flash_error("Couldn't build {} citation.".format(type))
            redirect(id)
