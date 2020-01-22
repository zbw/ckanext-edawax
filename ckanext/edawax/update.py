"""
Update package update field to allow for the invitation of a reviewer when
the dataset is created.
"""

import logging
import datetime

import ckan.logic as logic
import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckan.lib.dictization.model_save as model_save
import ckan.lib.navl.dictization_functions
import ckan.lib.plugins as lib_plugins
from ckan.common import _, request

import ckanext.edawax.helpers as h

log = logging.getLogger(__name__)

# Define some shortcuts
# Ensure they are module-private so that they don't get loaded as available
# actions in the action API.
_get_action = logic.get_action
_check_access = logic.check_access
NotFound = logic.NotFound
ValidationError = logic.ValidationError


def email_exists(email):
    users = tk.get_action('user_list')({'ignore_auth': True, 'keep_email': True}, {'all_fields': 'true'})
    for user in users:
        if user['email'] == email:
            return user['name']
    return False


def update_maintainer_field(user_name, data_dict, field):
    data_dict[field] = user_name
    return data_dict


def invite_reviewer(email, org_id):
    new_user = tk.get_action('user_invite')(None, {'email': email, 'group_id': org_id, 'role': 'reviewer'})
    return new_user

"""
def check_reviewer(data_dict, reviewer, field, new=False):
    #Check if a reviewer's email exsits. If so update field with name
    log.debug('Checking Reviewer: {}'.format(reviewer))
    if '@' in reviewer:
        email = reviewer
        # check that the email doesn't already belong to a user
        user_exists = email_exists(email)

        # if user exists, update field to contain user name
        # otherwise create the user and update the 'maintainer field. with
        # new name
        if user_exists:
            data_dict = update_maintainer_field(user_exists, data_dict, field)
            old = True
        # check if use is part of group, if not add them
        else:
            try:
                org_id = data_dict['organization']['id']
            except KeyError:
                org_id = data_dict['owner_org']
            new_user = invite_reviewer(email, org_id)
            data_dict = update_maintainer_field(new_user['name'], data_dict, field)
            old = False

    return data_dict, old
"""

def add_user_to_journal(data_dict, org_id, field, role='member'):
    # add new user to journal if they aren't in already
    org_data = tk.get_action('organization_show')(None, {'id': org_id})
    maintainer = data_dict.get(field)
    users = org_data['users']
    user_names = [user['name'] for user in users]
    if maintainer is not None and maintainer not in user_names:
        # if not in org, add them
        users = org_data['users']
        users.append({'name': maintainer, 'capacity': role})
        updated = tk.get_action('organization_patch')({'ignore_auth': True}, {'id': org_id, 'users': users})

    return True
