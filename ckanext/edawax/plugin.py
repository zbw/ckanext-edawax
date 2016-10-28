# Hendrik Bunke
# ZBW - Leibniz Information Centre for Economics

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
from ckanext.edawax import helpers
from ckan.logic.auth import get_package_object
from ckan.logic.auth.update import package_update as ckan_pkgupdate
# from collections import OrderedDict
import ckan.lib.helpers as h
from ckan.common import c
from toolz.functoolz import compose
from functools import partial

# XXX implement IAuthFunctions for controller actions


def edawax_facets(facets_dict):
    """
    helper method for common facet cleaning. We remove groups, tags and rename
    Organizations
    """
    try:
        del facets_dict['groups']
        del facets_dict['tags']
        del facets_dict['license_id']
        facets_dict.update({'organization': 'Journals'})
    except:
        pass
    return facets_dict


def get_facet_items_dict(facet, limit=None, exclude_active=False, sort_key='count'):
    '''
    Monkey-Patch of ckan/lib/helpers/get_facet_items_dict()
    CKANs sorting of facet items is hardcoded (https://github.com/ckan/ckan/issues/3271)
    Also: refactored to be a bit more functional (SCNR)
    '''

    try:
        f = c.search_facets.get(facet)['items']
    except:
        return []

    def active(facet_item):
        if not (facet, facet_item['name']) in tk.request.params.items():
            return dict(active=False, **facet_item)
        elif not exclude_active:
            return dict(active=True, **facet_item)

    def sort_facet(f):
        key = 'count'
        names = map(lambda i: i['name'], f)
        if sort_key == 'name' and any(map(str_to_int, names)):
            key = 'name'
        return sorted(f, key=lambda item: item[key], reverse=True)

    # for some reason limit is not in scope here, so it must be a param
    def set_limit(facs, limit):
        if c.search_facets_limits and limit is None:
            limit = c.search_facets_limits.get(facet)
        # zero treated as infinite for hysterical raisins
        if limit is not None and limit > 0:
            return facs[:limit]
        return facs

    filter_empty_name = partial(filter, lambda i: len(i['name'].strip()) > 0)
    isdict = partial(filter, lambda i: isinstance(i, dict))
    facets = compose(sort_facet, isdict, partial(map, active), filter_empty_name)(f)
    return set_limit(facets, limit)


def str_to_int(string):
    try:
        i = int(string)
    except:
        i = string
    return isinstance(i, int)


def journal_package_update(context, data_dict):
    """override ckan package_update"""
    user = context.get('auth_user_obj')
    package = get_package_object(context, data_dict)

    # always allow creator to update package, even if she is not allowed by
    # default org member permissions. 'create_dataset' permission must be set
    if package.creator_user_id and user.id == package.creator_user_id:
        return {'success': True}
    return ckan_pkgupdate(context, data_dict)


class EdawaxPlugin(plugins.SingletonPlugin,):
    '''
    edawax specific layout and workflow
    '''
    plugins.implements(plugins.IConfigurer, inherit=False)
    # plugins.implements(plugins.IDatasetForm, inherit=True)
    plugins.implements(plugins.ITemplateHelpers, inherit=True)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IFacets, inherit=True)
    plugins.implements(plugins.IRoutes, inherit=True)
    # plugins.implements(plugins.interfaces.IDomainObjectModification,
    #        inherit=True)  # XXX necessary?
    plugins.implements(plugins.IAuthFunctions)

    def update_config(self, config):
        tk.add_template_directory(config, 'templates')
        tk.add_public_directory(config, 'public')
        tk.add_template_directory(config, 'jdainfo/md')
        tk.add_resource('theme', 'edawax')
        tk.add_resource('fanstatic', 'edawax_fs')
        h.get_facet_items_dict = get_facet_items_dict

    def get_auth_functions(self):
        return {'package_update': journal_package_update}

    def get_helpers(self):
        return {'get_user_id': helpers.get_user_id,
                'show_review_button': helpers.show_review_button,
                'in_review': helpers.in_review,
                'is_private': helpers.is_private,
                'show_publish_button': helpers.show_publish_button,
                'show_retract_button': helpers.show_retract_button,
                'res_abs_url': helpers.res_abs_url,
                'pkg_abs_url': helpers.pkg_abs_url,
                'ckan_site_url': helpers.ckan_site_url,
                'journal_volume_sorting': helpers.journal_volume_sorting,
                'render_infopage': helpers.render_infopage,
                }

    def before_map(self, map):
        """
        replacing all organization urls with 'journal'
        """
        map.connect('organizations_index', '/journals', action='index',
                    controller='organization')

        map.connect('/journals/list', action='list', controller="organization")
        map.connect('/journals/new', action='new', controller="organization")

        map.connect('/journals/{action}/{id}',
                    requirements=dict(action='|'.join([
                        'edit',
                        'delete',
                        'admins',
                        'members',
                        'member_new',
                        'member_delete',
                        'history',
                        'bulk_process',
                        'about']
                    )),
                    controller="organization")

        map.connect('organization_activity', '/journals/activity/{id}',
                    action='activity', ckan_icon='time',
                    controller="organization")

        map.connect('organization_about', '/journals/about/{id}',
                    action='about', ckan_icon='info-sign', controller="organization")

        map.connect('organization_read', '/journals/{id}', action='read',
                    ckan_icon='sitemap', controller="organization")

        map.connect('user_dashboard_organizations', '/dashboard/journals',
                    action='dashboard_organizations', ckan_icon='building',
                    controller="user")

        # TODO redirects are just temporary, since there are still some routes
        # and links with 'organizations' in ckan. It even might be easier, to
        # simply redirect any organization url and leave the above maps out...
        map.redirect('/organization', '/journals')
        map.redirect('/organization/{url:.*}', '/journals/{url}')
        map.redirect('/dashboard/organizations', '/dashboard/journals')

        # review mail to editor
        map.connect('/dataset/{id}/review',
                    controller="ckanext.edawax.controller:WorkflowController",
                    action="review_mail",)

        # publish dataset
        map.connect('/dataset/{id}/publish',
                    controller="ckanext.edawax.controller:WorkflowController",
                    action="publish",)

        # retract dataset
        map.connect('/dataset/{id}/retract',
                    controller="ckanext.edawax.controller:WorkflowController",
                    action="retract",)

        # infopages
        controller = 'ckanext.edawax.controller:InfoController'
        map.connect('info', '/info',
                action="index",
                controller=controller,)
        map.connect('/info/{id}',
                action="md_page",
                controller=controller,)

        return map

    def organization_facets(self, facets_dict, organization_type, package_type):
        # for some reason CKAN does not accept a new OrderedDict here (does not happen
        # with datasets facets!). So we have to modify the original facets_dict

        KEY_VOLUME = 'dara_Publication_Volume'
        KEY_ISSUES = 'dara_Publication_Issue'

        edawax_facets(facets_dict)
        del facets_dict['organization']
        facets_dict.update({KEY_VOLUME: 'Volumes'})

        if tk.request.params.get(KEY_VOLUME, False):
            facets_dict.update({KEY_ISSUES: 'Issues'})

        # move formats at the end
        del facets_dict['res_format']
        facets_dict.update({'res_format': 'Formats'})

        return facets_dict

    def dataset_facets(self, facets_dict, package_type):
        KEY_VOLUME = 'dara_Publication_Volume'
        KEY_ISSUES = 'dara_Publication_Issue'
        edawax_facets(facets_dict)

        if tk.request.params.get('organization', False):
            facets_dict.update({KEY_VOLUME: 'Volumes'})
            if tk.request.params.get(KEY_VOLUME, False):
                facets_dict.update({KEY_ISSUES: 'Issues'})

            # move formats at the end
            del facets_dict['res_format']
            facets_dict.update({'res_format': 'Formats'})

        return facets_dict
