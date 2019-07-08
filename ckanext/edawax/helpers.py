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
    clean_list = [(" ".join(x[0].split(" ")[1:]), x[1]) for x in sorted_list]
    return clean_list


def chunk(lst, n):
    """ Generator to get evenly sized chunks from author list """
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def parse_authors(authors):
    out = ''
    if type(authors[0]) == dict:   #len(authors) > 1:
        return ' and '.join([u"{}, {}".format(author['lastname'].decode('unicode_escape'), author['firstname'].decode('unicode_escape')) for author in authors])
    if len(authors) > 5:
        return ' and '.join([u"{}, {}".format(c[0], c[1]) for c in chunk(authors, 5)])
    return u"{}, {}".format(authors[0], authors[1])


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
u"format": "96 Format",
u"url": "97 URL"}


def is_reviewer(pkg):
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
    user = c.userobj.name

    return user in reviewers


def is_admin():
    admins = c.group_admins
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
    return get_user_id() == pkg['creator_user_id'] and in_review(pkg) in ('false', 'reauthor')


def show_publish_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return check_journal_role(pkg, 'admin') and in_review(pkg) == 'true'


def show_retract_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return check_journal_role(pkg, 'admin') and not pkg.get('private', True)


def show_reauthor_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return check_journal_role(pkg, 'admin') and in_review(pkg) == 'true'


def show_notify_editor_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return in_review(pkg) == 'true' and is_reviewer(pkg)


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
