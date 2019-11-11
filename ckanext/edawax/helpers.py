# -*- coding: utf-8 -*-
import ckan.plugins.toolkit as tk
import ckan.model as model
from ckan.common import c, response, _, request
from ckanext.dara.helpers import check_journal_role
from pylons import config
from toolz.itertoolz import unique
from collections import namedtuple
import os
from ckan.lib import helpers as h
# from functools import wraps
import datetime
import collections
from ckan.lib import cli
import ast

import re
import ckanext.edawax.robot_list as _list
from urlparse import urlparse

from ckanext.dara.geography_coverage import geo


def get_manual_file():
    eng = config.get('ckan.doc_eng')
    deu = config.get('ckan.doc_deu')
    return (eng, deu)


def find_geographic_name(abbr):
    for country in geo:
        if country['value'] == abbr:
            return country['text'].capitalize()
    return ''


def format_resource_items_custom(items):
    out = []
    for item in items:
        if item[0] == u"dara_temporalCoverageFormal" and item[1] != u"":
            for thing in items:
                if thing[0] == u'dara_temporalCoverageFormal_end':
                    end = thing[1]
            out.append(( "9 Temporal Coverage (controlled)", "{} to {}".format(item[1], end) ))
        elif item[0] == u'dara_authors':
            if item[1] == "[u'', u'', u'', u'', u'']":
                package = tk.get_action('package_show')(None, {'id': request.url.split('/')[4]})
                authors = ast.literal_eval(package['dara_authors'])
                a = parse_authors(authors)
                out.append(("3 Authors", a))
            else:
                authors = item[1].decode('unicode_escape')
                authors = ast.literal_eval(authors)
                out.append(("3 Authors", parse_authors(authors)))
        elif item[0] == u'dara_geographicCoverage':
            countries = []
            try:
                parsed = ast.literal_eval(item[1])
            except ValueError:
                parsed = item[1]
            if type(parsed) == list:
                for country in parsed:
                    name = find_geographic_name(country)
                    countries.append(name)
            else:
                countries = [find_geographic_name(parsed)]
            out.append(("7 Geographic Area (controlled)", ", ".join(countries)))
        else:
            if item[0] in field_mapping.keys():
                out.append(( field_mapping[item[0]], item[1] ))

    sorted_list = sorted(out, key=lambda tup: tup[0])
    # remove the numbers from the field names
    clean_list = [(" ".join(x[0].split(" ")[1:]), x[1]) for x in sorted_list]
    return clean_list


def chunk(lst, n):
    """ Generator to get evenly sized chunks from author list """
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def parse_authors(authors):
    out = ''
    # information is coming from the dataset
    if type(authors[0]) == dict:   #len(authors) > 1:
        return ' and '.join([u"{}, {}".format(author['lastname'].decode('unicode_escape'), author['firstname'].decode('unicode_escape')) for author in authors])
    # Information is specific for the resource, and there's more than one
    # author
    if len(authors) > 5:
        temp_list = []
        for c in chunk(authors, 5):
            if c[0] != '':
                temp_list.append(u"{}, {}".format(c[0], c[1]))
            else:
                temp_list.append(u"{}".format(c[2]))
        return ' and '.join(temp_list)
    if authors[0] != u'':
        return u"{}, {}".format(authors[0], authors[1])
    return u"{}".format(authors[2])

# redo with a dictionary that contains the order?
# The dictionary would have the keys: position, field_name
# Then go through the dictionary and insert tuples based on the postion given
# in the dictionary? Too many moving parts?
# will also need a way to process the few things than need to be
# set - temporal coverage, authors, full geographic names

field_mapping = {u"dara_res_preselection": "1 Type",
u"dara_currentVersion": "2 Version",
u"dara_DOI": "4 DOI",
u"dara_PublicationDate": "5 Publication Date",
u"dara_Availabilitycontrolled": "6 Availability",
u"dara_geographicCoverageFree": "8 Geographic Area (free)",
u"dara_temporalCoverageFree": "91 Temporal Coverage (free)",
u"dara_unitType": "92 Unit Type",
u"dara_numberUnits": "93 Number of Units",
u"dara_universeSampled": "94 Sampled Universe",
u"dara_numberVariables": "95 Number of Variables",
u"url": "96 URL"}


def get_org_admin(org_id):
    admin = []
    try:
        org_data = tk.get_action('organization_show')(None, {'id': org_id})
    except Exception:
        return ''
    users = org_data['users']
    for user in users:
        if user['capacity'] == 'admin':
            admin.append(user['name'])

    return admin


def has_reviewers(pkg):
    reviewers = []
    try:
        reviewer = pkg.get('maintainer')
        reviewers.append(reviewer)
        reviewer = pkg.get('maintainer_email')
        reviewers.append(reviewer)
        return reviewers[0] is not None or reviewers[1] is not None
    except AttributeError as e:
        return False


def is_reviewer(pkg):
    # if there are no reviewers check that the journal editor / sysadmin is the user and give access
    reviewers = []
    try:
        reviewer = getattr(pkg, 'maintainer')
        reviewers.append(reviewer)
        reviewer = getattr(pkg, 'maintainer_email')
        reviewers.append(reviewer)
    except AttributeError:
        try:
            reviewer = pkg['maintainer']
            reviewers.append(reviewer)
            reviewer = pkg['maintainer_email']
            reviewers.append(reviewer)
        except Exception as e:
            return False

    if reviewers[0] not in [None, u''] and reviewers[1] not in [None, u'']:
        # add sysadmin
        if is_admin():
            reviewers.append(c.userobj.name)
        else:
            try:
                org_id = pkg['organization']['id']
                reviewers = get_org_admin(org_id)
            except TypeError as e:
                return False

    try:
        user = c.userobj.name
    except AttributeError as e:
        user = None

    return user in reviewers



def count_packages(packages):
    count = 0
    for package in packages:
        if not package['private'] or (package['private'] and is_admin()) or \
            (package['private'] and \
                get_user_id() == package['creator_user_id']):
            count += 1
    return count


def get_page_type():
    """
        Get page type to make breadcrumbs
    """
    action = request.urlvars['action']
    controller = request.urlvars['controller']
    id_ = request.urlvars.get('id', None)
    resource_id = request.urlvars.get('resource_id', None)

    try:
        pkg = tk.get_action('{}_show'.format(controller))(None, {'id': id_})
    except:
        pkg = None

    if resource_id:
        resource = tk.get_action('resource_show')(None, {'id': resource_id})
        resource_name = resource['name']
    else:
        resource_name = 'Resource'

    try:
        if 'organization' in pkg.keys():
            journal = pkg['organization']['title']
            parent = pkg['organization']
            resource = pkg
        else:
            parent = None
            resource = None
    except (AttributeError, TypeError):
        parent = None
    resource = pkg

    ignore = False
    if action == 'search':
        text = "Datasets"
    elif action == 'index':
        if controller == 'organization':
            text = 'Journals'
        else:
            text = 'Home'
            ignore = True
    elif action == 'read':
        try:
            text = pkg['title']
        except KeyError:
            # working with user name
            text = id_
    elif action == 'resource_read':
        text = resource_name
    elif action == 'new':
        if controller == 'package':
            text = 'Dataset'
        elif controller == 'organization':
            text = 'Journal'
    elif action == 'dashboard_read':
        text = 'Stats'
    elif action in ['dashboard', 'dashboard_datasets', 'dashboard_organizations', 'logged_in']:
        text = 'Dashboard'
    elif action == 'edit':
        if controller == 'user':
            text = id_
        elif controller == 'organization':
            text = 'Admin'
        else:
            text = 'Edit'
    elif action == 'resource_edit':
        text = 'Edit'
    elif action == 'login':
        text = 'Login'
    elif action == 'register':
        text = 'Registration'
    elif action == 'logged_out_page':
        text = 'Logged Out'
        ignore = True
    elif action == 'request_reset':
        text = 'Password reset'
    elif action == 'activity':
        text = 'Activity'
    elif action == 'about':
        text = 'About'
    elif action == 'md_page':
        text = 'Info'
        ignore = True
    elif action in ['resources', 'doi', 'new_resource']:
        text = 'Resources'
        ignore = True
    elif action in ['bulk_process', 'members']:
        text = 'Admin'
        action = 'edit'
    else:
        text = ''
        ignore = True
        #raise ValueError('This wasnt accounted for: {}'.format(action))

    return {'text': text,'action': action, 'controller': controller, 'id': id_, 'resource_id': resource_id, 'parent': parent, 'resource': resource,
         'ignore': False}


def normal_height():
    path = request.upath_info
    pages = ['/', '/user/login', '/user/logged_out_redirect', '/user/reset']
    if path in pages:
        return False
    return True


def pkg_status(id):
    pkg = tk.get_action('package_show')(None, {'id': id})
    return pkg['dara_edawax_review']

def tags_exist(data):
    pkg = tk.get_action('package_show')(None, {'id': data.current_package_id})
    if pkg['tags'] != []:
        return True
    return False

def is_landing_page():
    if 'edit' in request.url or '/dataset/resources' in request.url:
        return False
    return True

def is_edit_page():
    if ('edit' in request.url or 'views' in request.url) and not ('user/edit' in request.url or 'journals/edit' in request.url or 'dataset/edit' in request.url):
        return True

    return False


def is_admin(pkg=None):
    admins = c.group_admins

    if pkg:
        org_id = pkg['owner_org']
        admins = get_org_admin(org_id)
        try:
            user_id = c.userobj.name
        except Exception:
            return False
        if user_id in admins:
            return True

    try:
        user_id = c.userobj.id
        if user_id in admins:
            return True
    except AttributeError as e:
        pass
    return False


def has_doi(pkg):
    if pkg:
        doi = pkg.get('dara_DOI', False) or pkg.get('dara_DOI_Test', False)
        if doi in ['', False]:
            return False
        return True
    return False


def has_hammer():
    return c.is_sysadmin


def is_published(url):
    parts = urlparse(url)
    if '/journals/' in parts.path:
        return True
    start = 9
    if len(parts.path) > 36:
        end = 36 + start
        dataset_name = parts.path[start:end]
    else:
        dataset_name = parts.path[start:]

    try:
        pck = tk.get_action('package_show')(None, {'id': dataset_name})
        if is_private(pck) or in_review(pck) != 'reviewed':
            return False
        return True
    except Exception as e:
        return False


def track_path(path):
    if '/journals/' in path or '/download/' in path:
        return True
    if '/dataset' in path and '/resource' not in path:
        return True
    return False


def is_robot(user_agent):
    robots = _list.robots
    for robot in robots:
        pattern = re.compile(robot['pattern'], re.IGNORECASE)
        if pattern.search(user_agent):
            return True
    return False


def truncate_title(name):
    if len(name) > 30:
        base = name[0:23]
        ending = name[-3:]
        return u'{}...{}'.format(base, ending)
    return name


def get_resource_name(data):
    """
        Return a list of dicts (name, url, package_id, resource_id)
        or the ID of the package which will be used to provide a link
        to add a resource for instances when none exist.
    """
    output = []
    for resource in data['resources']:
        output.append(resource['id'])
    if len(output) == 0:
        return data['id']
    return output


def transform_to_map(data):
    """
        data: list of resource ids
        returns: list of dicts with resource data

        Each dict contains the information needed by the popup to provide
        the required information.
    """
    try:
        final = []
        lst = ast.literal_eval(data)
        for item in lst:
            _id = item
            resource_data = tk.get_action('resource_show')(None, {'id':_id})
            data = {
                       'name': resource_data['name'],
                       'url': resource_data['url'],
                       'package_id': resource_data['package_id'],
                       'resource_id': resource_data['id'],
                       'format': resource_data['format']
                    }
            final.append(data)
        return final
    except Exception:
        pass
    return data


def get_user_id():
    def context():
        return {'model': model, 'session': model.Session,
                'user': c.user or c.author, 'for_view': True,
                'auth_user_obj': c.userobj}
    user = tk.c.user
    if not user:
        return
    converter = tk.get_converter('convert_user_name_or_id_to_id')
    return converter(tk.c.user, context())


def in_review(pkg):
    if not isinstance(pkg, dict):
        return 'false'
    return pkg.get('dara_edawax_review', 'false')


def is_private(pkg):
    if not isinstance(pkg, dict):
        return True
    return pkg.get('private', True)


def show_review_button(pkg):
    return (is_admin(pkg) and in_review(pkg) in ('reauthor', 'finished', 'editor'))  or (get_user_id() == pkg['creator_user_id'] and in_review(pkg) in ['false', 'reauthor']) or (has_hammer() and not in_review(pkg) in ['reviewers', 'reviewed']) and not pkg.get('private', True)


def show_manage_button(pkg):
    """
        Show for:
            * Admins/Editors always:
            * Authors, before admins/editors have it
    """
    if not isinstance(pkg, dict):
        return False
    # always allow admins
    if has_hammer() or is_admin(pkg):
        return True
    # authors should only be able to edit in first stage or reauthor
    if in_review(pkg) not in ['false', 'reauthor']:
        return not get_user_id() == pkg['creator_user_id']
    else:
        return get_user_id() == pkg['creator_user_id']


def show_publish_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return (check_journal_role(pkg, 'admin') or has_hammer()) and in_review(pkg) in ['true', 'reviewers', 'finished', 'editor']


def show_retract_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return (check_journal_role(pkg, 'admin') or has_hammer()) and not pkg.get('private', True)


def show_reauthor_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return (check_journal_role(pkg, 'admin') or has_hammer()) and in_review(pkg) in ['true', 'finished', 'editor', 'reviewers']


def show_notify_editor_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return in_review(pkg) in ['reviewers'] and (has_hammer() or \
        is_reviewer(pkg))


def res_abs_url(res):
    return res['url'].partition('download/')[0]


def pkg_abs_url(pkg):
    site_url = config.get('ckan.site_url')
    pkg_url = tk.url_for(controller='package', action='read', id=pkg['name'])
    return site_url + pkg_url


def ckan_site_url():
    return config.get('ckan.site_url', 'http://journaldata.zbw.eu')


def journal_volume_sorting(packages):
    """
    return namedtuple for package sorting with volume/issue as key
    """
    v = 'dara_Publication_Volume'
    i = 'dara_Publication_Issue'

    def t_construct(vi):
        VIP = namedtuple('VIP', 'volume issue packages')
        pf = filter(lambda d: d.get(v, '') == vi[0] and d.get(i, '') == vi[1], packages)
        return VIP(vi[0], vi[1], pf)

    sort = tk.request.params.get('sort', False)
    if sort == u'{} desc, {} desc'.format(v, i):
        vi_list = map(lambda d: (d.get(v, ''), d.get(i, '')), packages)
        return map(t_construct, unique(vi_list))

    return False


def render_infopage(page):
    template_paths = config['pylons.app_globals'].template_paths
    for path in template_paths:
        if os.path.exists(os.path.join(path, page.encode('utf-8'))):
            return h.render_markdown(tk.render(page), allow_html=True)
    tk.abort(404, "Markdown file not found")


def journal_total_views(org):
    url = org['name']
    result = _total_journal_views(engine, target=url)
    if len(result) > 0:
        return result[0].count
    else:
        return 0


def journal_recent_views(org):
    measure_from = datetime.date.today() - datetime.timedelta(days=14)
    url = org['name']
    result =  _recent_journal_views(engine, measure_from=measure_from, target=url)
    if len(result) > 0:
        return result[0].count
    else:
        return 0


def dataset_total_views(pkg):
    result = _total_data_views(engine)
    for r in result:
        if r.name == pkg['name']:
            return r.count
    return 0


def dataset_recent_views(pkg):
    measure_from = datetime.date.today() - datetime.timedelta(days=14)
    result = _recent_data_views(engine, measure_from)
    for r in result:
        if r.name == pkg['name']:
            return r.count
    return 0


def resource_downloads(resource):
    url = resource
    sql = """
            SELECT COALESCE(SUM(ts.count), 0) as total_views
            FROM tracking_summary as ts
            WHERE ts.url = %(url)s;
          """
    results = engine.execute(sql, url=url).fetchall()

    return results[0][0]


#===========================================================#
# The following come from ckan/lib/cli.py                   #
# They need to be changed to work with 'url' rather than ID #
# to get the counts for JOURNALs, rather than datasets      #
#===========================================================#
import ckan.model as model
engine = model.meta.engine

_ViewCount = collections.namedtuple("ViewCount", "id name count")

def _total_journal_views(engine, target):
    sql = '''
        SELECT p.id,
               p.name,
               COALESCE(SUM(ts.count), 0) AS total_views
        FROM "group" AS p
        CROSS JOIN tracking_summary AS ts
        WHERE p.name = %(name)s
            AND ts.url = %(url)s
        GROUP BY p.id, p.name
        ORDER BY total_views DESC
    '''

    return [_ViewCount(*t) for t in engine.execute(sql, {'name': target, 'url': '/journals/' + target }).fetchall()]


def _recent_journal_views(engine, target, measure_from):
    sql = '''
        SELECT p.id,
               p.name,
               COALESCE(SUM(ts.count), 0) AS total_views
           FROM "group" AS p
           CROSS JOIN tracking_summary AS ts
           WHERE ts.tracking_date >= %(measure_from)s
                AND p.name = %(name)s
                    AND ts.url = %(url)s
           GROUP BY p.id, p.name
           ORDER BY total_views DESC
    '''
    return [_ViewCount(*t) for t in engine.execute(sql, name=target, url='/journals/{}'.format(target), measure_from=str(measure_from)).fetchall()]


def _total_data_views(engine):
    sql = '''
        SELECT p.id,
               p.name,
               COALESCE(SUM(s.count), 0) AS total_views
           FROM package AS p
           LEFT OUTER JOIN tracking_summary AS s ON s.package_id = p.id
           GROUP BY p.id, p.name
           ORDER BY total_views DESC
    '''
    return [_ViewCount(*t) for t in engine.execute(sql).fetchall()]


def _recent_data_views(engine, measure_from):
    sql = '''
        SELECT p.id,
               p.name,
               COALESCE(SUM(s.count), 0) AS total_views
           FROM package AS p
           LEFT OUTER JOIN tracking_summary AS s ON s.package_id = p.id
           WHERE s.tracking_date >= %(measure_from)s
           GROUP BY p.id, p.name
           ORDER BY total_views DESC
    '''
    return [_ViewCount(*t) for t in engine.execute(sql, measure_from=str(measure_from)).fetchall()]


def show_download_all(pkg):
    count = 0
    if not isinstance(pkg, dict):
        return False
    for resource in pkg['resources']:
        rsc = tk.get_action('resource_show')(None, {'id': resource['id']})
        if rsc.get('url_type') == 'upload':
            count += 1
    return count > 1
