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

log = logging.getLogger(__name__)

# Define some shortcuts
# Ensure they are module-private so that they don't get loaded as available
# actions in the action API.
_get_action = logic.get_action
_check_access = logic.check_access
NotFound = logic.NotFound
ValidationError = logic.ValidationError


def email_exists(email):
    users = tk.get_action('user_list')(None, {'all_fields': 'true'})
    for user in users:
        if user['email'] == email:
            return user['name']
    return False


def update_maintainer_field(user_name, data_dict):
    data_dict['maintainer'] = user_name
    return data_dict


def invite_reviewer(email, org_id):
    new_user = tk.get_action('user_invite')(None, {'email': email, 'group_id': org_id, 'role': 'reviewer'})
    return new_user


def package_update(context, data_dict):
    '''This is a modified version of the package_update that will create a
    reviewer and invite them to the JDA

    Update a dataset (package).

    You must be authorized to edit the dataset and the groups that it belongs
    to.

    It is recommended to call
    :py:func:`ckan.logic.action.get.package_show`, make the desired changes to
    the result, and then call ``package_update()`` with it.

    Plugins may change the parameters of this function depending on the value
    of the dataset's ``type`` attribute, see the
    :py:class:`~ckan.plugins.interfaces.IDatasetForm` plugin interface.

    For further parameters see
    :py:func:`~ckan.logic.action.create.package_create`.

    :param id: the name or id of the dataset to update
    :type id: string

    :returns: the updated dataset (if ``'return_package_dict'`` is ``True`` in
              the context, which is the default. Otherwise returns just the
              dataset id)
    :rtype: dictionary

    '''
    # handle reviewer
    # if the 'maintainer' is an email, check if a user has that email
    # if there is a user with the email, update the maintainer field
    # otherwise, don't do anything - leave the email as the maintainer.
    #
    reviewer_1 = data_dict.get("maintainer", None)
    reviewer_2 = data_dict.get("maintainer_email", None)
    reviewers = [reviewer_1, reviewer_2]
    if reviewer_1 != '' or reviewer_2 != '':
        if (reviewer_1 is not None and reviewer_2 is not None) and ('@' in reviewer_1 or '@' in reviewer_2):
            for reviewer in reivewers:
                if '@' in reviewer:
                    email = reviewer
                    # check that the email doesn't already belong to a user
                    user_exists = email_exists(email)

                    # if user exists, update field to contain user name
                    # otherwise create the user and update the 'maintainer field. with
                    # new name
                    if user_exists:
                        data_dict = update_maintainer_field(user_exists, data_dict)
                        # needs to receive an email now? I think not
                        # check if use is part of group, if not add them

                    else:
                        try:
                            org_id = data_dict['organization']['id']
                        except KeyError:
                            org_id = data_dict['owner_org']

            #new_user = invite_reviwer(email, org_id)
            #data_dict = update_mainter_field(new_user['name'], data_dict)
        else:
            # check that user is member of the organization
            try:
                org_id = data_dict['organization']['id']
            except KeyError:
                org_id = data_dict['owner_org']
            org_data = tk.get_action('organization_show')(None, {'id': org_id})
            maintainer = data_dict.get("maintainer")
            users = org_data['users']
            user_names = [user['name'] for user in users]
            if maintainer is not None and maintainer not in user_names:
                # if not in org, add them
                users = org_data['users']

                users.append({'name': maintainer, 'capacity': 'member'})
                updated = tk.get_action('organization_patch')({'ignore_auth': True}, {'id': org_id, 'users': users})

    model = context['model']
    user = context['user']
    name_or_id = data_dict.get("id") or data_dict['name']


    pkg = model.Package.get(name_or_id)
    if pkg is None:
        raise NotFound(_('Package was not found.'))
    context["package"] = pkg
    data_dict["id"] = pkg.id
    data_dict['type'] = pkg.type

    _check_access('package_update', context, data_dict)

    # get the schema
    package_plugin = lib_plugins.lookup_package_plugin(pkg.type)
    if 'schema' in context:
        schema = context['schema']
    else:
        schema = package_plugin.update_package_schema()

    if 'api_version' not in context:
        # check_data_dict() is deprecated. If the package_plugin has a
        # check_data_dict() we'll call it, if it doesn't have the method we'll
        # do nothing.
        check_data_dict = getattr(package_plugin, 'check_data_dict', None)
        if check_data_dict:
            try:
                package_plugin.check_data_dict(data_dict, schema)
            except TypeError:
                # Old plugins do not support passing the schema so we need
                # to ensure they still work.
                package_plugin.check_data_dict(data_dict)

    data, errors = lib_plugins.plugin_validate(
        package_plugin, context, data_dict, schema, 'package_update')
    log.debug('package_update validate_errs=%r user=%s package=%s data=%r',
              errors, context.get('user'),
              context.get('package').name if context.get('package') else '',
              data)

    if errors:
        model.Session.rollback()
        raise ValidationError(errors)

    rev = model.repo.new_revision()
    rev.author = user
    if 'message' in context:
        rev.message = context['message']
    else:
        rev.message = _(u'REST API: Update object %s') % data.get("name")

    #avoid revisioning by updating directly
    model.Session.query(model.Package).filter_by(id=pkg.id).update(
        {"metadata_modified": datetime.datetime.utcnow()})
    model.Session.refresh(pkg)

    pkg = model_save.package_dict_save(data, context)

    context_org_update = context.copy()
    context_org_update['ignore_auth'] = True
    context_org_update['defer_commit'] = True
    _get_action('package_owner_org_update')(context_org_update,
                                            {'id': pkg.id,
                                             'organization_id': pkg.owner_org})

    # Needed to let extensions know the new resources ids
    model.Session.flush()
    if data.get('resources'):
        for index, resource in enumerate(data['resources']):
            resource['id'] = pkg.resources[index].id

    for item in plugins.PluginImplementations(plugins.IPackageController):
        item.edit(pkg)

        item.after_update(context, data)

    # Create default views for resources if necessary
    if data.get('resources'):
        logic.get_action('package_create_default_resource_views')(
            {'model': context['model'], 'user': context['user'],
             'ignore_auth': True},
            {'package': data})

    if not context.get('defer_commit'):
        model.repo.commit()

    log.debug('Updated object %s' % pkg.name)

    return_id_only = context.get('return_id_only', False)

    # Make sure that a user provided schema is not used on package_show
    context.pop('schema', None)

    # we could update the dataset so we should still be able to read it.
    context['ignore_auth'] = True
    output = data_dict['id'] if return_id_only \
            else _get_action('package_show')(context, {'id': data_dict['id']})

    return output
