import ckan.plugins as plugins
import ckan.plugins.toolkit as tk


# Our custom template helper function.
#def example_helper():
#    '''An example template helper function.'''
#
#    # Just return some example text.
#    return 'This is some example text.'

class EdawaxThemePlugin(plugins.SingletonPlugin, ):
    '''An example that shows how to use the ITemplateHelpers plugin interface.

    '''
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)

    # Update CKAN's config settings, see the IConfigurer plugin interface.
    def update_config(self, config):
        """
        """
        tk.add_template_directory(config, 'templates')
        tk.add_public_directory(config, 'public')
        tk.add_resource('theme', 'edawax')


    # Tell CKAN what custom template helper functions this plugin provides,
    # see the ITemplateHelpers plugin interface.
    def get_helpers(self):
        return {}
