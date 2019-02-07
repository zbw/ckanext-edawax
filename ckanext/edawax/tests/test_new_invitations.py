"""
Tests implementation of new method for sending invitation emails.
It should be possible to use different templates for the emailes
based on the users role.
"""
import pylons.test, pylons, pylons.config as c, ckan.model as model, ckan.tests as tests, ckan.plugins as plugins, ckan.tests.factories as factories
from ckan.tests import helpers
import ckanext.edawax.new_invites as i
pylons.app_globals._push_object(c['pylons.app_globals'])

class TestNewInvites(object):

    @classmethod
    def setup_class(cls):
        plugins.load('edawax')

    def teardown(self):
        model.repo.rebuild_db()

    @classmethod
    def teardown_class(cls):
        plugins.unload('edawax')

    def _create_test_user(self, role):
        org = factories.Organization()
        member = model.User(name=u'tester', apikey=u'tester', password=u'tester')
        test_member = {'username': member.name,
           'role': role,
           'group_id': org['id'],
           'email': 'member@zbw.eu',
           'journal_title': org['title']}
        return (member, test_member)

    def _test_choose_correct_email_body_for_member(self):
        member, test_member = self._create_test_user(u'member')
        result = i.get_invite_body(member, test_member)
        assert 'deposit the replication' in result, ('Wrong Template: {}').format(result)

    def _test_choose_correct_email_body_for_editor(self):
        member, test_member = self._create_test_user(u'editor')
        result = i.get_invite_body(member, test_member)
        assert 'to serve as an additional editor' in result, ('Wrong Template: {}').format(result)
    """
    def test_new_member_invitation(self):
        member, test_member = self._create_test_user('member')
        result = helpers.call_action('user_invite', **test_member)
        assert result != None, ('Result: {}').format(result)
        return
    """
