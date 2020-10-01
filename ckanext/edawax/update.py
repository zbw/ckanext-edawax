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
from ckan.common import _, request, c, g
from ckan import model

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


def update_maintainer_field(user_name, email, data_dict):
    context = {'model': model, 'session': model.Session,
                'user': g.user or g.author, 'for_view': True,
                'auth_user_obj': g.userobj, 'ignore_auth': True}
    data_dict['maintainer'] = "{}/{}".format(email, user_name)
    updated_dict = tk.get_action('package_patch')(context, data_dict)

    return updated_dict


def invite_reviewer(email, org_id):
    log.debug("Inviting: {}".format(email))
    new_user = tk.get_action('user_invite')(None, {'email': email, 'group_id': org_id, 'role': 'reviewer'})
    return new_user


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
