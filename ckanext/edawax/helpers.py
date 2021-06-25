# -*- coding: utf-8 -*-
import os
import six
import json
import hashlib
import sqlalchemy as sa

import ckan.plugins.toolkit as tk
import ckan.model as model
from ckan.common import c, g, streaming_response, _, request, config
from ckanext.dara.helpers import check_journal_role
from toolz.itertoolz import unique
from collections import namedtuple
from ckan.lib import helpers as h
# from functools import wraps
import datetime
import collections
import ast
import requests

import flask
from flask import Response as resp
from flask import make_response

import re
import ckanext.edawax.robot_list as _list
from urllib.parse import urlparse

from ckan.authz import get_group_or_org_admin_ids

from ckanext.dara.geography_coverage import geo

import logging
log = logging.getLogger(__name__)


def pkg_status(id):
    pkg = tk.get_action('package_show')(None, {'id': id})
    return pkg['dara_edawax_review']

def get_manual_file():
    eng = config.get('ckan.doc_eng', 'manual_EN.pdf')
    deu = config.get('ckan.doc_deu', 'manual_DE.pdf')
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
            out.append(( "9 Temporal Coverage (controlled)", f"{item[1]} to {end}"))
        elif item[0] == u'dara_authors':
            if item[1] in ["[u'', u'', u'', u'', u'']", "['']", ['', '', '', '', '']]:
                package = tk.get_action('package_show')({'use_cache': False}, {'id': request.url.split('/')[4]})
                try:
                    authors = ast.literal_eval(package['dara_authors'].replace("null", '""'))
                except Exception:
                    authors = ast.literal_eval(package['extras_dara_authors'].replace("null", '""'))
                a = parse_authors(authors)
                out.append(("3 Authors", a))
            else:
                try:
                    authors = item[1]
                    if isinstance(authors, list):
                        authors = authors
                    else:
                        authors = ast.literal_eval(authors)
                    out.append(("3 Authors", parse_authors(authors)))
                except AttributeError as e:
                    authors = [""]
                    out.append(("3 Authors", ""))
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
                if item[0] in replacement_list:
                    try:
                        int(item[1])
                        value = replacement_values[item[0]][item[1]]
                    except ValueError:
                        value = item[1]
                else:
                    value = item[1]
                out.append(( field_mapping[item[0]], value ))

    sorted_list = sorted(out, key=lambda tup: tup[0])
    # remove the numbers from the field names
    clean_list = [(" ".join(x[0].split(" ")[1:]), x[1]) for x in sorted_list]
    return clean_list


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def parse_authors(authors):
    out = ''
    # information is coming from the dataset
    if type(authors[0]) == dict:   #len(authors) > 1:
        return u' and '.join([f"{author['lastname']}, {author['firstname']}" for author in authors])
    # Information is specific for the resource, and there's more than one
    # author
    if len(authors) > 5:
        temp_list = []
        for c in chunk(authors, 5):
            if c[0] != '':
                temp_list.append(f"{c[0]}, {c[1]}")
            else:
                temp_list.append(f"{c[2]}")
        return ' and '.join(temp_list)
    if authors[0] != u'':
        return f"{authors[0]}, {authors[1]}"
    return f"{authors[2]}"

# fields with number values in older records that need to be replaced by strings
replacement_list = [
    u'dara_Availabilitycontrolled',
    u'dara_unitType'
]
replacement_values = {
    u'dara_Availabilitycontrolled': {
                                        '1': 'Download',
                                        '2': 'OnSite',
                                        '3': 'OnSite'
                                    },
    u'dara_unitType': {
                        '1': 'Individual',
                        '2': 'Organization',
                        '3': 'Family',
                        '4': 'Family: Household Familiy',
                        '5': 'Household',
                        '6': 'Housing Unit',
                        '7': 'Event/Process',
                        '8': 'Geographic Unit',
                        '9': 'Time Unit',
                        '10': 'Text Unit',
                        '11': 'Group',
                        '12': 'Object',
                        '13': 'Other'
                    },
}

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


def delete_cookies(pkg):
    #Clear Cookies - after resend
    try:
        cookie = f"reviewerPrev_{pkg['name']}"
        #request.cookies.get(f"reviewerPrev_{pkg['name']}", False)
        r = make_response('Response')
        r.delete_cookie(cookie)
        return r
    except Exception as e:
        log.debug(f'delete_cookies error: {e}')


def _existing_user(pkg):
    """ Check if given reviewer is an existing user """
    user_emails = [obj.email for obj in model.User.all()]
    if '/' in pkg['maintainer']:
        reviewer_email, reviewer_name = pkg['maintainer'].split('/')
    else:
        reviewer_email = pkg['maintainer']

    if reviewer_email in user_emails:
        return True
    return False

def check_reviewer_update(pkg):
    """Check if the reviewer is new or not"""
    reviewer_change = request.cookies.get(f"reviewerPrev_{pkg['name']}", False)
    if reviewer_change == 'new':
        return True

    return False


def get_org_admin(org_id):
    try:
        Entity = model.User
        q = model.Session.query(Entity.name).\
               join(model.Member, model.Member.table_id == Entity.id).\
               filter(model.Member.group_id == org_id).\
               filter(model.Member.state == 'active').\
               filter(model.Member.table_name == 'user').\
               filter(model.Member.capacity == 'admin')
    except Exception as e:
        log.debug(f'get_org_admin error: {e}')
        return ''

    return [name[0] for name in q.all()]


def hide_from_reviewer(pkg):
    return is_reviewer(pkg) and is_private(pkg)


def has_reviewers(pkg):
    reviewers = []
    try:
        reviewer = pkg.get('maintainer')
        reviewers.append(reviewer)
        return reviewers[0] not in [None, '']
    except AttributeError as e:
        log.debug(f'has_reviewers error: {e} {e.message} {e.args}')
        return False


def is_reviewer(pkg):
    reviewers = []

    try:
        reviewer = getattr(pkg, 'maintainer')
    except AttributeError as e:
        try:
            reviewer = pkg['maintainer']
        except Exception as e:
            if pkg:
                log.debug(f'is_reviewer error: {e} {e.message} {e.args}')
            return False

    emails = []
    names = []

    if not reviewer:
        return False

    if '/' in reviewer:
        email, name = reviewer.split('/')
        emails.append(email)
        names.append(name)
    else:
        email = reviewer
        emails.append(email)

    try:
        user = g.userobj.name
        email = g.userobj.email
    except AttributeError as e:
        user = None
        email = None
        return False
    #email = model.User.get(user).email
    return user in names or email in emails

def is_author(pkg):
    return get_user_id() == pkg['creator_user_id']


def count_packages(packages):
    count = 0
    for package in packages:
        if not package['private'] or (package['private'] and is_admin()) or \
            (package['private'] and \
                get_user_id() == package['creator_user_id']):
            count += 1
    return count


def normal_height():
    path = request.path
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
    if '/edit/' in request.url or '/dataset/resources' in request.url:
        return False
    return True

def is_edit_page():
    if ('/edit/' in request.url or 'views' in request.url) \
        and not ('user/edit' in request.url or 'journals/edit' in request.url \
            or 'dataset/edit' in request.url or 'views_recent' in request.url):
        return True

    return False


def is_admin(pkg=None):
    if g.userobj is None:
        return False
    if has_hammer():
        return True

    if pkg:
        org_id = pkg['owner_org']
        admins = get_org_admin(org_id)
        try:
            user_id = g.userobj.name
        except Exception:
            return False
        if user_id in admins:
            return True

    from sqlalchemy import and_
    if hasattr(g, 'group'):
        group_id = g.group.id
    else:
        try:
            group_id = g.pkg.owner_org
        except Exception:
            return False
    admins = model.Session.query(model.Member).filter(and_(model.Member.capacity == 'admin',
                            model.Member.group_id == group_id)).all()

    try:
        user_id = g.userobj.id
        if user_id in [a.table_id for a in admins]:
            return True
    except AttributeError as e:
        log.debug(f'is_admin error: {e} {e.message} {e.args}')
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
    try:
        return g.userobj.sysadmin == True
    except AttributeError as e:
        return False


def is_published(url):
    parts = urlparse(url)
    if '/journals/' in parts.path:
        return True

    start = 9
    if '/edit/' in parts.path:
        start += 5

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


def track_download(url, filename, key):
    prefix = config.get('ckan.site_url', 'http://127.0.0.1:5000')
    actor = f'Ckan-Download-All::'
    user_key = f'{actor}{key}'
    engine = sa.create_engine(config.get('sqlalchemy.url'))
    sql = '''INSERT INTO tracking_raw
                (user_key, url, tracking_type)
                VALUES (%s, %s, %s)'''
    try:
        engine.execute(sql, user_key, url, 'resource')
        return True, None
    except Exception as e:
        return False, e


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
        if pattern.search(str(user_agent)):
            return True
    return False


def truncate_title(name):
    if len(name) > 30:
        base = name[0:23]
        ending = name[-3:]
        return f'{base}...{ending}'
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
        log.debug('transform_to_map error: {e} {e.message} {e.args}')

    return data


def get_user_id():
    def context():
        return {'model': model, 'session': model.Session,
                'user': g.user or g.author, 'for_view': True,
                'auth_user_obj': g.userobj}
    user = g.user
    if not user:
        return
    converter = tk.get_converter('convert_user_name_or_id_to_id')
    return converter(user, context())


def in_review(pkg):
    if not isinstance(pkg, dict):
        return 'false'
    return pkg.get('dara_edawax_review', 'false')


def is_private(pkg):
    if not isinstance(pkg, dict):
        return True
    return pkg.get('private', True)


def is_author(pkg):
    return get_user_id() == pkg['creator_user_id']

def show_change_reviewer(pkg):
    return in_review(pkg) == 'reviewers' and (is_admin(pkg) or has_hammer())

def show_review_button(pkg):
    """
    When to show:
        For sys admin-always
        for journal admin-once sent to admin by author
        for author-after initial creation
        for reviewer-
    """
    return (get_user_id() == pkg['creator_user_id'] and in_review(pkg) in ['false', 'reauthor']) \
        or (has_hammer() and not in_review(pkg) in ['reviewers', 'reviewed']) \
            or (is_admin(pkg) and not (in_review(pkg) in ['false', 'reauthor', 'reviewers', 'reviewed']))



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
    if in_review(pkg) in ['false', 'reauthor']:
        return get_user_id() == pkg['creator_user_id']

    return False


def show_publish_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return (check_journal_role(pkg, 'admin') or has_hammer()) \
        and in_review(pkg) in ['true', 'reviewers', 'finished', 'editor', 'back']


def show_retract_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return (check_journal_role(pkg, 'admin') or has_hammer()) and not pkg.get('private', True)


def show_reauthor_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return (check_journal_role(pkg, 'admin') or has_hammer()) \
        and in_review(pkg) in ['true', 'finished', 'editor', 'reviewers', 'back']


def show_notify_editor_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return in_review(pkg) in ['reviewers'] and (has_hammer() \
        or is_reviewer(pkg))


def res_abs_url(res):
    package_id = res['package_id']
    resource_id = res['id']
    return f'/dataset/{package_id}/resource/{resource_id}'


def pkg_abs_url(pkg):
    site_url = config.get('ckan.site_url')
    pkg_url = tk.url_for('dataset.read', id=pkg['name'])
    return site_url + pkg_url


def ckan_site_url():
    return config.get('ckan.site_url', 'https://journaldata.zbw.eu')


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

    sort = request.args.get('sort', False)
    if sort == f'{v} desc, {i} desc':
        vi_list = map(lambda d: (d.get(v, ''), d.get(i, '')), packages)
        return map(t_construct, unique(vi_list))

    return False


def render_infopage(page):
    template_paths = config['computed_template_paths']
    for path in template_paths:
        if os.path.exists(os.path.join(path, page)):
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
    result = _total_data_views(engine, pkg['name'])
    try:
        return result[0].count
    except Exception:
        return 0


def dataset_recent_views(pkg):
    measure_from = datetime.date.today() - datetime.timedelta(days=14)
    result = _recent_data_views(engine, measure_from, pkg['name'])
    try:
        return result[0].count
    except Exception:
        return 0


def resource_downloads(resource):
    url = resource
    if url != '':
        sql = """
                SELECT COALESCE(SUM(ts.count), 0) as total_views
                FROM tracking_summary as ts
                WHERE ts.url = %(url)s;
            """
        results = engine.execute(sql, url=url).fetchall()

        return results[0][0]
    return 0


def find_reviewers_datasets(name):
    if not name:
        return []
    # the double %% are required by Python, otherwise it thinks is string formating
    sql = """
            SELECT package.id, package.title
            FROM package
            INNER JOIN "user" as u
            ON package.maintainer ILIKE '%%' || u.name || '%%'
            INNER JOIN member
            ON member.table_id = u.id
            INNER JOIN package_extra as pe
            ON package.id = pe.package_id
            WHERE member.capacity = 'reviewer'
            AND u.name = %(name)s
            AND package.private = 't'
            AND pe.key = 'dara_edawax_review'
            AND pe.value = 'reviewers'
            GROUP BY package.id;
          """
    results = engine.execute(sql, {'name':name}).fetchall()

    out = [{'id': result[0],
            'name': result[1].title()} for result in results]

    return out

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
    return [_ViewCount(*t) for t in engine.execute(sql, name=target, url=f'/journals/{target}', measure_from=str(measure_from)).fetchall()]


def _total_data_views(engine, target):
    sql = '''
        SELECT p.id,
               p.name,
               COALESCE(SUM(s.count), 0) AS total_views
           FROM package AS p
           LEFT OUTER JOIN tracking_summary AS s ON s.package_id = p.id
           WHERE p.name = %(name)s
           GROUP BY p.id, p.name
           ORDER BY total_views DESC
    '''
    return [_ViewCount(*t) for t in engine.execute(sql, name=target).fetchall()]


def _recent_data_views(engine, measure_from, target):
    sql = '''
        SELECT p.id,
               p.name,
               COALESCE(SUM(s.count), 0) AS total_views
           FROM package AS p
           LEFT OUTER JOIN tracking_summary AS s ON s.package_id = p.id
           WHERE s.tracking_date >= %(measure_from)s
                AND p.name = %(name)s
           GROUP BY p.id, p.name
           ORDER BY total_views DESC
    '''
    return [_ViewCount(*t) for t in engine.execute(sql, measure_from=str(measure_from), name=target).fetchall()]


def show_download_all(pkg):
    count = 0
    if not isinstance(pkg, dict):
        return False
    for resource in pkg['resources']:
        if resource['url_type'] == 'upload':
            count += 1
            if count > 1:
                return True
    return count > 1

"""
The following are used to create/update information regarding related
publications. the information is stored in the package "notes" field
which hasn't been utilized yet.
"""
def query_crossref(doi):
    """
        Plan to only run this if there's a DOI but the publication
        metadata is incomplete.
    """
    if not is_robot(request.user_agent):  # don't run for bots to limit api usage
        base_url = "https://api.crossref.org/works/{doi}"
        headers = {
            'User-Agent': 'ZBW-JDA (https://journaldata.zbw.eu); mailto:journaldata@zbw.eu',
            'From': 'journaldata@zbw.eu'
        }

        try:
            response = requests.get(base_url.format(doi=doi),
                                    headers=headers, timeout=5)
        except requests.exceptions.Timeout as e:
            log.debug(f'query_crossref error: {e}')
            return False
        if response.status_code == 200:
            return response.json()['message']
    return False


def build_citation_crossref(doi):
    """
        build citation from CrossRef JSON
    """
    def not_none(x):
        return x is not None

    data = query_crossref(doi)
    citation = u"{authors} ({year}). {title}. {journal}, {volume}({issue}). doi: <a href='https://doi.org/{doi}'>{doi}</a>"

    if data:
        try:
            fields = {
                "authors": u", ".join(filter(not_none,
                                     map(parse_author, data['author']))),
                "year"   : data['created']['date-parts'][0][0],
                "title"  : data['title'][0],
                "journal": data['container-title'][0],
                "volume" : data['volume'],
                "issue"  : data['issue'],
                "doi"    : data['DOI']
            }
            return citation.format(**fields)
        except KeyError as e:
            log.debug(f'build_citation_crossref error: {e}')

    return ""


def parse_author(author):
    # differentiate between people and institutions
    if 'given' in author.keys():
        return f"{author['family']}, {author['given'][0]}."


def update_citation(data):
    if data['dara_Publication_PIDType'] in ['DOI', 'doi']:
        temp = data['dara_Publication_PID']
        new_citation = build_citation_crossref(data['dara_Publication_PID'])
        correct_citation = correct(new_citation)
        context = {'model': model, 'session': model.Session,
                    'user': g.user or g.author, 'for_view': True,
                    'auth_user_obj': g.userobj, 'ignore_auth': True}
        data = {'id': data['id'], 'dara_related_citation': correct_citation}
        try:
            if correct_citation != '':
                tk.get_action('package_patch')(context, data)
        except Exception as e:
            log.debug(f'update_citation error: {e}')

        return correct_citation
    else:
        return ''


def correct(citation):
    """Correct known errors in CrossRef Data"""
    #VSWG has an issue in CrossRef where the ü is replaced with ??
    fixed = citation
    if u'Vierteljahrschrift' in citation and u'f??r' in citation:
        fixed = citation.replace(u'f??r', u'für')

    return fixed

# ---------------------------------------------------
# Functions for adding schema.org metadata to the page
# ----------------------------------------------------
def build_citation_local(pkg):
    citation = '{authors} ({year}): {title}. Version {version}. {journal}. Dataset. {url}'

    if 'dara_authors' not in pkg.keys():
        return ''

    if not hide_from_reviewer(pkg):
        for author in ast.literal_eval(pkg['dara_authors'].replace("null", '""')):
            if author == pkg['dara_authors'][-1]:
                a = ', '.join(author['lastname'], author['firstname'])
            else:
                a = f"{author['lastname']}, {author['firstname']}"
    else:
        a = "Witheld for Review"
    year = pkg['dara_PublicationDate']
    title = pkg['title']
    version = pkg['dara_currentVersion']
    journal = pkg['organization']['title']
    url = f'{config.get("ckan.site_url", "http://127.0.0.1:5000")}/dataset/{pkg["id"]}'

    return citation.format(authors=a, year=year, title=title, version=version, journal=journal, url=url)


def guess_mimetype(rsc):
    """Some resources are missing the "mimetype"
    """
    file_name, file_ext = os.path.splitext(rsc['name'])
    if rsc['mimetype'] is None and file_ext:
        import mimetypes
        try:
            type_ = mimetypes.types_map[file_ext]
        except KeyError:
            try:
                type_ = mimetypes.types_map[file_ext.lower()]
            except KeyError:
                return file_ext
        return type_
    elif rsc['url_type'] is None:
        return 'text/uri-list'
    else:
        return rsc['mimetype']


def make_schema_metadata(pkg):
    # There is a minimum of 50 characters for a descripion according to Google's
    # "Rich Results Test". This should make sure there is enough
    if pkg['notes'] == '':
        description = f'Replication data stored in the Journal Data Archive for \"{pkg["title"]}\".'
    elif len(pkg['notes']) < 50:
        description = f'{pkg["notes"]} - stored in the Journal Data Archive.'
    else:
        description = pkg['notes']
    base = {
                '@context':'http://schema.org',
                '@type':'Dataset',
                '@id': pkg.get('dara_DOI') if pkg.get('dara_DOI') != '' else f'{config.get("ckan.site_url", "http://127.0.0.1:5000")}/dataset/{pkg["id"]}',
                'identifier': pkg.get('dara_DOI') if pkg.get('dara_DOI') != '' else pkg['id'],
                'name': pkg['title'],
                'datePublished': pkg.get('metadata_created', ''),
                'dateModified': pkg.get('metadata_modified', ''),
                'version': pkg['dara_currentVersion'],
                'description': description,
                'keywords': [x['display_name'] for x in pkg.get('tags')],
                'citation':{
                        '@type':'CreativeWork',
                        'text': build_citation_local(pkg),
                        'name': pkg['title']
                },
                'license':{
                    "@type":"CreativeWork",
                    "url":"http://creativecommons.org/licenses/by/4.0",
                    "text":"CC BY 4.0"
                },
                'includedInDataCatalog':{
                    '@type':'DataCatalog',
                    'name':'Journal Data Archive',
                    'url':'https://journaldata.zbw.eu'
                },
                'publisher':{
                    '@type':'Organization',
                    'name':'ZBW - Leibniz Informationszentrum Wirtschaft'
                },
                'provider':{
                    '@type':'Organization',
                    'name':'ZBW - Leibniz Informationszentrum Wirtschaft'
                },
                'author': None,
                'creator': None,
                'distribution': None
            }
    a = []
    if 'dara_authors' not in pkg.keys():
        a.append({"@type":"Person","name": f"Name"})
    else:
        for author in ast.literal_eval(pkg['dara_authors'].replace("null", '""')):
            a.append({"@type":"Person","name": f"{author['firstname']} {author['lastname']}"})
    base['author'] = a
    base['creator'] = a
    r = []
    for resource in pkg['resources']:
        r.append({
            "@type":"DataDownload",
            "name": resource['name'],
            "encodingFormat": guess_mimetype(resource),
            "contentSize": resource.get('size', 0),
            "description": resource['description'],
            "@id": resource['id'],
            "identifier": f'{config.get("ckan.site_url", "http://127.0.0.1:5000")}/dataset/{pkg["id"]}/resource/{resource["id"]}',
            "contentUrl": resource['url']
        })
    base['distribution'] = r

    if not test_server_private(pkg):
        return json.dumps(base)
    return ''

def test_server_private(pkg):
    return '134.245' in config.get("ckan.site_url") and not is_private(pkg)