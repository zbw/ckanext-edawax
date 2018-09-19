"""
The included functions are an attempt to decouple the invitation system
from the core CKAN code. Additionally, it provides for a way to send
invitations based on the role of the invitee.

Role of the new user gets passed down to functions so that a decision can
be made about which template to use of the email.
"""
import ckan, random
from pylons import config
import ckan.lib.mailer as mailer, ckan.logic.action.create as logic
from ckan.lib.base import render_jinja2

def get_invite_body(user, data=None):
    extra_vars = {'reset_link': mailer.get_reset_link(user),
       'site_title': config.get('ckan.site_title'),
       'user_name': user.name,
       'site_url': config.get('ckan.site_url'),
       'journal_title': data['journal_title']}

    if data['role'] == u'editor':
        return render_jinja2('emails/invite_editor.txt', extra_vars)
    return render_jinja2('emails/invite_author.txt', extra_vars)


def send_invite(user, data):
    mailer.create_reset_key(user)
    body = get_invite_body(user, data=data)
    subject = mailer._('Invite for {site_title}').format(site_title=mailer.g.site_title)
    mailer.mail_user(user, subject, body)


def user_invite(context, data_dict):
    """
    Recreated from logic.create with one addition to pass the user's data
    to send_invite
    """
    logic._check_access('user_invite', context, data_dict)
    schema = context.get('schema', ckan.logic.schema.default_user_invite_schema())
    data, errors = logic._validate(data_dict, schema, context)
    if errors:
        raise logic.ValidationError(errors)
    name = logic._get_random_username_from_email(data['email'])
    password = str(random.SystemRandom().random())
    data['name'] = name
    data['password'] = password
    data['state'] = ckan.model.State.PENDING
    user_dict = logic._get_action('user_create')(context, data)
    user = ckan.model.User.get(user_dict['id'])
    member_dict = {'username': user.id,
       'id': data['group_id'],
       'role': data['role']}
    org_info = logic._get_action('organization_show')(context, member_dict)
    data['journal_title'] = org_info['display_name']
    logic._get_action('group_member_create')(context, member_dict)
    send_invite(user, data)
    return logic.model_dictize.user_dictize(user, context)
