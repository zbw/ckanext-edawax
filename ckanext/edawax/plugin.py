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


def get_facet_items_dict(facet, limit=None, exclude_active=False, sort_key='item_count'):
    '''
    Monkey-Patch! CKANs sorting of facet items is hardcoded. See
    https://github.com/ckan/ckan/issues/3271

    Return the list of unselected facet items for the given facet, sorted
    by count.

    Returns the list of unselected facet contraints or facet items (e.g. tag
    names like "russian" or "tolstoy") for the given search facet (e.g.
    "tags"), sorted by facet item count (i.e. the number of search results that
    match each facet item).

    Reads the complete list of facet items for the given facet from
    c.search_facets, and filters out the facet items that the user has already
    selected.

    Arguments:
    facet -- the name of the facet to filter.
    limit -- the max. number of facet items to return.
    exclude_active -- only return unselected facets.

    '''
    request = tk.request
    if not c.search_facets or \
            not c.search_facets.get(facet) or \
            not c.search_facets.get(facet).get('items'):
        return []
    facets = []
    for facet_item in c.search_facets.get(facet)['items']:
        if not len(facet_item['name'].strip()):
            continue
        if not (facet, facet_item['name']) in request.params.items():
            facets.append(dict(active=False, **facet_item))
        elif not exclude_active:
            facets.append(dict(active=True, **facet_item))

    # facets = sorted(facets, key=lambda item: item['count'], reverse=True)
    def sort_facets(key):
        return sorted(facets, key=lambda item: item[key], reverse=True)

    if sort_key == 'item_title':
        def title_to_int(title):
            """only sort with title when it is a number
            """
            try:
                return int(title)
            except:
                return title

        title = facet_item['name']
        if isinstance(title_to_int(title), int):
            facets = sort_facets('name')
        else:
            facets = sort_facets('count')

    else:
        facets = sort_facets('count')

    if c.search_facets_limits and limit is None:
        limit = c.search_facets_limits.get(facet)
    # zero treated as infinite for hysterical raisins
    if limit is not None and limit > 0:
        return facets[:limit]
    return facets



# XXX in controller
# def send_mail_to_editors(entity, operation):
#    """
#   submit notification to mailer
#   """
#   user_id, user_name = tk.c.userobj.id, tk.c.userobj.fullname
#
#   if not user_name:
#       user_name = tk.c.userobj.email  # otherwise None

#   ops = {'new': 'created', 'changed': 'updated', 'deleted': 'deleted'}
#   op = ops[operation]

#   # get list of journal editors. Current user will not be notified
#   org_admins = filter(lambda x: x != user_id,
#                       get_group_or_org_admin_ids(entity.owner_org))

#   # get email address of journal editors
#   addresses = map(lambda admin_id: model.User.get(admin_id).email, org_admins)
#
#   # send notification to all addresses
#   map(lambda a: notification(a, user_name, entity.id, op), addresses)


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
                }

    def before_map(self, map):
        """
        replacing all organization urls with 'journal'
        """
        map.connect('organizations_index', '/journals', action='index',
                controller='organization')
        map.connect('/journals/list', action='list',
        controller="organization")
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
            'about',
          ])), controller="organization"
          )
        map.connect('organization_activity', '/journals/activity/{id}',
                  action='activity', ckan_icon='time',
                  controller="organization")
        map.connect('organization_about', '/journals/about/{id}',
                  action='about', ckan_icon='info-sign', controller="organization")
        map.connect('organization_read', '/journals/{id}', action='read',
                  ckan_icon='sitemap', controller="organization")
        map.connect('user_dashboard_organizations', '/dashboard/journals',
                  action='dashboard_organizations', ckan_icon='building', controller="user")

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

        return map

    def organization_facets(self, facets_dict, organization_type, package_type):
        # for some reason CKAN does not accept a new OrderedDict here. So we have to
        # modify the original facets_dict

        key_volume = 'dara_Publication_Volume'
        key_issues = 'dara_Publication_Issue'
        volume_in_request = tk.request.params.get(key_volume, False)

        edawax_facets(facets_dict)
        del facets_dict['organization']
        facets_dict.update({key_volume: 'Volumes'})

        if volume_in_request:
            facets_dict.update({key_issues: 'Issues'})

        formats = facets_dict.popitem(last=False)
        facets_dict.update(dict([formats]))

        return facets_dict

    def dataset_facets(self, facets_dict, package_type):
        return edawax_facets(facets_dict)
