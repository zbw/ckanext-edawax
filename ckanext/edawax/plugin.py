import ckan.plugins as plugins
import ckan.plugins.toolkit as tk



class EdawaxThemePlugin(plugins.SingletonPlugin, ):
    '''An example that shows how to use the ITemplateHelpers plugin interface.

    '''
    plugins.implements(plugins.IConfigurer)
    #plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IFacets, inherit=True)
    plugins.implements(plugins.IRoutes, inherit=True)

    # Update CKAN's config settings, see the IConfigurer plugin interface.
    def update_config(self, config):
        """
        """
        tk.add_template_directory(config, 'templates')
        tk.add_public_directory(config, 'public')
        tk.add_resource('theme', 'edawax')


    # Tell CKAN what custom template helper functions this plugin provides,
    # see the ITemplateHelpers plugin interface.
    #def get_helpers(self):
    #    return {}

    #XXX debugging methods

    # def after_update(self,context, pkg_dict):
    #     """
    #     test
    #     """
    #     import ipdb; ipdb.set_trace()

    #def before_view(self, pkg_dict):
    #    import ipdb; ipdb.set_trace()

    
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

        #TODO redirects are just temporary, since there are still some routes
        #and links with 'organizations' in ckan. It even might be easier, to
        #simply redirect any organization url and leave the above maps out...
        map.redirect('/organization', '/journals')
        map.redirect('/organization/{url:.*}', '/journals/{url}')
        map.redirect('/dashboard/organizations', '/dashboard/journals')

        return map


       #map.connect('stats', '/stats',
       #    controller='ckanext.stats.controller:StatsController',
       #    action='index')
       #map.connect('stats_action', '/stats/{action}',
       #    controller='ckanext.stats.controller:StatsController')
       #return map

       


    def organization_facets(self, facets_dict,  organization_type, package_type):
        """
        modify facets. We remove groups, tags and rename 'organizations'
        'Journals'
        """
        facets = self.__edawax_facets(facets_dict)
        return facets

    def dataset_facets(self, facets_dict, package_type):
        ''' Update the facets_dict and return it. we remove groups, tags and
        rename Organizations
        '''
        facets = self.__edawax_facets(facets_dict)
        return facets

    
    def __edawax_facets(self, facets_dict):
        """
        helper method for common facet cleaning
        """
        try: 
            del facets_dict['groups']
            del facets_dict['tags']
            facets_dict['organization'] = 'Journals'
        except:
            pass
        
        return facets_dict


