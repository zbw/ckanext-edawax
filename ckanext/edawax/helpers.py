import ckan.plugins.toolkit as tk
import ckan.model as model
from ckan.common import c
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


def get_resource_name(data):
    """
        Return a list of dicts (name, url, package_id, resource_id)
        Or the ID of the package which will be used to provide a link
        to add a resource for instances when none exist.
    """
    output = []
    for resource in data['resources']:
        output.append({'name': resource['name'],
                       'url': resource['url'],
                       'package_id': data['id'],
                       'resource_id': resource['id'],
                       'format': resource['format']})
    if len(output) == 0:
        return data['id']
    return output


def transform_to_map(data):
    try:
        lst = ast.literal_eval(data)
        return lst
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

#===========================================================
# The following come from ckan/lib/cli.py
# They need to be changed to work with 'url' rather than ID
# to get the counts for JOURNALs, rather than datasets
#===========================================================
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
