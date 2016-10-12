import ckan.plugins.toolkit as tk
import ckan.model as model
from ckan.common import c
import ckanext.dara.helpers as dara_helpers
from pylons import config
from toolz.itertoolz import unique
from collections import namedtuple


# decorator might useful for future
# def type_check(t):
#   def decorator(func):
#       def wrapper(*args):
#           if isinstance(args[0], t):
#               return func(*args)
#           return False
#       return wrapper
#   return decorator


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


def show_review_button(pkg):
    return get_user_id() == pkg['creator_user_id'] and in_review(pkg) == 'false'


def in_review(pkg):
    if not isinstance(pkg, dict):
        return 'false'
    return pkg.get('dara_edawax_review', 'false')


def is_private(pkg):
    if not isinstance(pkg, dict):
        return True
    return pkg.get('private', True)


def show_publish_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return dara_helpers.check_journal_role(pkg, 'admin') and pkg.get('private', True)


def show_retract_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return dara_helpers.check_journal_role(pkg, 'admin') and not pkg.get('private', True)


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
