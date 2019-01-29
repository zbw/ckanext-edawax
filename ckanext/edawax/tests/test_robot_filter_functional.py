"""
Functional tests for robot filter
"""

import pylons.test, pylons, pylons.config as c, ckan.model as model, ckan.plugins as plugins, ckan.tests.factories as factories
import paste
import paste.fixture
from ckan.tests import helpers
from ckan.lib.helpers import url_for
import datetime
import ckan
import webtest

import random


class TestTrackingFunctional(helpers.FunctionalTestBase):
    """
    some of the helper functions are taken/adapted from the legacy test for teacking
    """
    def teardown(self):
        model.repo.rebuild_db()


    @classmethod
    def teardown_class(cls):
        if plugins.plugin_loaded('edawax'):
            plugins.unload('edawax')


    def _get_app(self):
        c['global_conf']['debug'] = 'true'
        app = ckan.config.middleware.make_app(c['global_conf'], **c)
        app = webtest.TestApp(app)
        if not plugins.plugin_loaded('edawax'):
            plugins.load('edawax')
        return app


    def _update_tracking_summary(self):
        '''Update CKAN's tracking summary data.
        This simulates calling `paster tracking update` on the command line.
        '''
        import ckan.lib.cli
        import ckan.model
        date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(
            '%Y-%m-%d')
        ckan.lib.cli.Tracking('Tracking').update_all(
            engine=ckan.model.meta.engine, start_date=date)


    def _post_to_tracking(self, url, type_='page', ip='199.204.138.90',
                          browser='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'):
        '''Post some data to /_tracking directly.

        This simulates what's supposed when you view a page with tracking
        enabled (an ajax request posts to /_tracking).

        '''
        app = self._get_app()
        params = {'url': url, 'type': type_}
        extra_environ = {
            # The tracking middleware crashes if these aren't present.
            'HTTP_USER_AGENT': browser,
            'REMOTE_ADDR': ip,
            'HTTP_ACCEPT_LANGUAGE': 'en',
            'HTTP_ACCEPT_ENCODING': 'gzip, deflate',
        }

        app.post(str(url), params=params, extra_environ=extra_environ)


    def _create_package_resource(self, resource=False):
        user = factories.User()
        owner_org = factories.Organization(users=[{'name': user['id'], 'capacity': 'admin'}])
        dataset = factories.Dataset(owner_org=owner_org['id'])
        if resource:
            resource = factories.Resource(package_id=dataset['id'])
            return dataset, resource
        return dataset


    def test_dataset_0_views(self):
        """ Hasn't been viewed yet """
        dataset = self._create_package_resource()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)
        tracking_summary = package['tracking_summary']

        assert tracking_summary['total'] == 0, 'Total should be 0, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 0, 'Recent should be 0, {}'.format(tracking_summary['recent'])


    def test_dataset_1_view_real(self):
        """ 1 view """
        dataset = self._create_package_resource()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        url = url_for(controller='package', action='read',
                             id=package['name'])
        self._post_to_tracking(url)
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)
        tracking_summary = package['tracking_summary']

        assert tracking_summary['total'] == 1, 'Total should be 1, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 1, 'Recent should be 1, {}'.format(tracking_summary['recent'])

    def test_dataset_3_view_real(self):
        """ multiple views from different users """
        dataset = self._create_package_resource()
        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        url = url_for(controller='package', action='read',
                             id=package['name'])

        for ip in ['44', '55', '66']:
            self._post_to_tracking(url, ip='111.222.333.{}'.format(ip))
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)
        tracking_summary = package['tracking_summary']

        assert tracking_summary['total'] == 3, 'Total should be 3, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 3, 'Recent should be 3, {}'.format(tracking_summary['recent'])

    def test_dataset_1_view_bot(self):
        """ 1 view from a bot, shouldn't be counted """
        dataset = self._create_package_resource()
        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)
        url = url_for(controller='package', action='read',
                             id=package['name'])

        self._post_to_tracking(url, browser='bot')
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)
        tracking_summary = package['tracking_summary']

        assert tracking_summary['total'] == 0, 'Total should be 0, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 0, 'Recent should be 0, {}'.format(tracking_summary['recent'])

    def test_dataset_3_view_bot(self):
        """ Multiple views from bots shouldn't be counted """
        dataset = self._create_package_resource()
        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        url = url_for(controller='package', action='read',
                             id=package['name'])

        for ip in ['44', '55', '66']:
            self._post_to_tracking(url, ip='111.222.333.{}'.format(ip), browser='bot')
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)
        tracking_summary = package['tracking_summary']

        assert tracking_summary['total'] == 0, 'Total should be 0, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 0, 'Recent should be 0, {}'.format(tracking_summary['recent'])


    def test_resource_0_views(self):
        """ should be 0 """
        dataset, resource = self._create_package_resource(True)

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        resource = package['resources'][0]
        tracking_summary = resource['tracking_summary']

        assert tracking_summary['total'] == 0, 'Total should be 0 {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 0, 'Recent should be 0, {}'.format(tracking_summary['recent'])


    def test_resource_1_view_real(self):
        """ Viewing a resource shouldn't count """
        dataset, resource = self._create_package_resource(True)
        url = resource['url']

        self._post_to_tracking(url)
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        resource = package['resources'][0]

        tracking_summary = resource['tracking_summary']

        assert tracking_summary['total'] == 0, 'Total should be 0, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 0, 'Recent should be 0, {}'.format(tracking_summary['recent'])


    def _test_resource_1_download_real(self):
        """ Download from 1 user """
        dataset, resource = self._create_package_resource(True)
        url = resource['url']

        self._post_to_tracking(url, type_='resource')
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        resource = package['resources'][0]

        tracking_summary = resource['tracking_summary']

        assert tracking_summary['total'] == 1, 'Total should be 1, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 1, 'Recent should be 1, {}'.format(tracking_summary['recent'])

    def _test_resource_1_download_bot(self):
        """ Downlaod from a bot, shouldn't count """
        dataset, resource = self._create_package_resource(True)
        url = resource['url']

        self._post_to_tracking(url, type_='resource', browser='bot')
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        resource = package['resources'][0]

        tracking_summary = resource['tracking_summary']

        assert tracking_summary['total'] == 0, 'Total should be 0, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 0, 'Recent should be 0, {}'.format(tracking_summary['recent'])


    def _test_resource_3_downloads_diff_users_real(self):
        """ Multiple downloads from different users """
        dataset, resource = self._create_package_resource(True)
        url = resource['url']

        for ip in ['44', '55', '66']:
            self._post_to_tracking(url, type_='resource', ip='111.222.333.{}'.format(ip))
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        resource = package['resources'][0]

        tracking_summary = resource['tracking_summary']

        assert tracking_summary['total'] == 3, 'Total should be 3, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 3, 'Recent should be 3, {}'.format(tracking_summary['recent'])


    def _test_resource_3_downloads_same_user_real(self):
        """ Multiple downloads from different users """
        dataset, resource = self._create_package_resource(True)
        url = resource['url']

        for ip in ['44', '44', '44']:
            self._post_to_tracking(url, type_='resource', ip='111.222.333.{}'.format(ip))
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        resource = package['resources'][0]

        tracking_summary = resource['tracking_summary']

        assert tracking_summary['total'] == 1, 'Total should be 1, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 1, 'Recent should be 1, {}'.format(tracking_summary['recent'])

    def _test_resource_3_downloads_bots(self):
        """ Multiple downloads from bots, shouldn't count """
        dataset, resource = self._create_package_resource(True)
        url = resource['url']

        for ip in ['44', '55', '66']:
            self._post_to_tracking(url, type_='resource', ip='111.222.333.{}'.format(ip), browser='bot')
        self._update_tracking_summary()

        package = helpers.call_action('package_show', id=dataset['id'], include_tracking=True)

        resource = package['resources'][0]

        tracking_summary = resource['tracking_summary']

        assert tracking_summary['total'] == 0, 'Total should be 0, {}'.format(tracking_summary['total'])
        assert tracking_summary['recent'] == 0, 'Recent should be 0, {}'.format(tracking_summary['recent'])



