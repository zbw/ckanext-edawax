# Hendrik Bunke
# ZBW - Leibniz Information Centre for Economics

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckan.model as model
from ckan.authz import get_group_or_org_admin_ids
from ckanext.edawax import helpers
from ckanext.mail import notification


def edawax_facets(facets_dict):
    """
    helper method for common facet cleaning. We remove groups, tags and rename
    Organizations
    """
    try:
        del facets_dict['groups']
        del facets_dict['tags']
        facets_dict.update({'organization': 'Journals'})
    except:
        pass
    return facets_dict


def send_mail_to_editors(entity, operation):
    """
    submit notification to mailer
    """
    user_id, user_name = tk.c.userobj.id, tk.c.userobj.fullname
    ops = {'new': 'created', 'changed': 'updated', 'deleted': 'deleted'}
    op = ops[operation]

    # get list of journal editors. Current user will not be notified
    org_admins = filter(lambda x: x != user_id,
                        get_group_or_org_admin_ids(entity.owner_org))

    # get email address of journal editors
    addresses = map(lambda admin_id: model.User.get(admin_id).email, org_admins)
    
    # send notification to all addresses
    map(lambda a: notification(a, user_name, entity.id, op), addresses)


class EdawaxPlugin(plugins.SingletonPlugin, ):
    '''
    edawax specific layout and workflow
    '''
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers, inherit=True)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IFacets, inherit=True)
    plugins.implements(plugins.IRoutes, inherit=True)
    plugins.implements(plugins.interfaces.IDomainObjectModification, inherit=True)


    def update_config(self, config):
        tk.add_template_directory(config, 'templates')
        tk.add_public_directory(config, 'public')
        tk.add_resource('theme', 'edawax')

    def get_helpers(self):
        return {'get_user_id': helpers.get_user_id}

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

        return map

    def organization_facets(self, facets_dict, organization_type, package_type):
        return edawax_facets(facets_dict)

    def dataset_facets(self, facets_dict, package_type):
        return edawax_facets(facets_dict)

    def notify(self, entity, operation):
        """
        we might need several functions in case of modifications, so this one
        just calls them
        """
        # only send mails for Packages, and only for active ones (= no drafts)
        if isinstance(entity, model.package.Package) and entity.state == 'active':
            send_mail_to_editors(entity, operation)

    
