"""
The included functions are an attempt to decouple the invitation system
from the core CKAN code. Additionally, it provides for a way to send
invitations based on the role of the invitee.

Role of the new user gets passed down to functions so that a decision can
be made about which template to use of the email.
"""
import ckan, random
import ckan.lib.mailer as mailer
import ckan.logic.action.create as logic
from ckan.lib.base import render

import ckan.plugins.toolkit as tk
#imports for expanded mailing
import os
import smtplib
import logging
from time import time
from email import utils
from ckan.common import _, g, request, config, asbool
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

import ckanext.edawax.helpers as h
import ckan.lib.helpers as helpers

log = logging.getLogger(__name__)


class MailerException(Exception):
    pass


def _get_user_role(user_name, org_id):
    data_dict = {'id': org_id}
    org_data = user_data = ckan.logic.get_action('organization_show')(data_dict=data_dict)
    users = org_data['users']
    for user in users:
        if user['name'] == user_name:
            return user['capacity']
    return False


def get_invite_body(user, data=None):
    try:
        id_ = data['group_id']
    except Exception as e:
        log.error('Error Creating invite -couldn\'t find group_id in data- {e}')
        id_ = request.view_args['id']
    site_url = config.get('ckan.site_url')
    url_ = tk.url_for("dataset.read", id=id_)
    url = f"{site_url}{url_}"

    extra_vars = {'reset_link': mailer.get_reset_link(user),
       'site_title': config.get('ckan.site_title'),
       'user_name': user.name,
       'site_url': config.get('ckan.site_url'),
       'journal_title': data['journal_title'],
       'url': url,
       'man_eng': h.get_manual_file()[0],
       'man_deu': h.get_manual_file()[1]}

    role = _get_user_role(user.name, data['group_id'])
    if role in ['editor', 'admin']:
        return render('emails/invite_editor.txt', extra_vars)
    elif role == 'reviewer':
        return render('emails/invite_reviewer.txt', extra_vars)
    return render('emails/invite_author.txt', extra_vars)


def send_invite(user, data):
    mailer.create_reset_key(user)
    body = get_invite_body(user, data=data)
    # pass role to mail function to check if the attachement should be sent
    role = data['role']
    if role == u'member':
        role = "Author"
    elif role == u'admin':
        role = "Editor"
    else:
        role = "Reviewer"
    sub = config.get('ckan.site_title')
    subject = mailer._(f'{sub} Invite: {role}')
    mail_user(user, subject, body, {}, role)


def user_invite(context, data_dict):
    """
    Recreated from logic.create with one addition to pass the user's data
    to send_invite
    """
    log.debug(f"--Starting Invitation Process--")
    log.debug(f"{data_dict}")
    logic._check_access('user_invite', context, data_dict)
    schema = context.get('schema', ckan.logic.schema.default_user_invite_schema())
    data, errors = logic._validate(data_dict, schema, context)
    log.error(f'Errors: {errors}')
    if errors:
        raise logic.ValidationError(errors)
    name = logic._get_random_username_from_email(data['email'])
    password = str(random.SystemRandom().random())
    data['name'] = name
    data['password'] = password
    data['state'] = ckan.model.State.PENDING
    try:
        user_dict = logic._get_action('user_create')(context, data)
        log.debug(f"Created new user: {user_dict['id']}")
        user = ckan.model.User.get(user_dict['id'])
        member_dict = {'username': user.id,
                    'id': data['group_id'],
                    'role': data['role']}
        org_info = logic._get_action('organization_show')(context, member_dict)
        data['journal_title'] = org_info['display_name']
        logic._get_action('group_member_create')(context, member_dict)
        log.debug(f"Sending Invite")
        send_invite(user, data)
        return logic.model_dictize.user_dictize(user, context)
    except ckan.logic.ValidationError as e:
        log.error(f"Ran into ValidationError: {e}")
        return {'name': False}


# modifying CKAN's base mail function to allow sending attachments
def _mail_recipient(recipient_name, recipient_email,
        sender_name, sender_url, subject,
        body, headers={}, role=None):
    mail_from = config.get('smtp.mail_from')
    if role:
        if role in [u'member', 'Author']:
            recipient_name = "Author"
        elif role in [u'Reviewer', 'reviewer']:
            recipient_name = "Reviewer"
        else:
            recipient_name = "Editor"
    else:
        recipient_name = recipient_name
    #body = mailer.add_msg_niceties(recipient_name, body, sender_name, sender_url)
    msg_body = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    msg = MIMEMultipart()
    for k, v in headers.items(): msg[k] = v
    subject = Header(subject.encode('utf-8'), 'utf-8')
    msg['Subject'] = subject
    msg['From'] = _("%s <%s>") % (sender_name, mail_from)
    recipient = u"%s <%s>" % (recipient_name, recipient_email)
    msg['To'] = Header(recipient)
    msg['Date'] = utils.formatdate(time())
    msg['X-Mailer'] = "CKAN %s" % ckan.__version__

    msg.attach(msg_body)

    # attach the file
    if role is not None and role in [u'member', 'Author', 'Editor', 'Reviewer']:
        if role in [u'member', 'Author']:
            attachment_file_name = "QuickManual_V1.5.pdf"
        elif role in ['Reviewer']:
            attachment_file_name = "Manual_for_reviewers_V1-1.5.2.pdf"
        else:
            attachment_file_name = "Editors_Manual-EN-2020-07-31_V1.6.pdf"
        directory = os.path.dirname(__file__)
        rel_path = f'public/{attachment_file_name}'
        with open(os.path.join(directory, rel_path), 'rb') as file:
            part = MIMEApplication(
                                    file.read(),
                                    name=attachment_file_name
                                  )
        part['Content-Disposition'] = f'attachment; filename={attachment_file_name}'
        msg.attach(part)

    # Send the email using Python's smtplib.
    smtp_connection = smtplib.SMTP()
    if 'smtp.test_server' in config:
        # If 'smtp.test_server' is configured we assume we're running tests,
        # and don't use the smtp.server, starttls, user, password etc. options.
        smtp_server = config['smtp.test_server']
        smtp_starttls = False
        smtp_user = None
        smtp_password = None
    else:
        smtp_server = config.get('smtp.server', 'localhost')
        smtp_starttls = asbool(config.get('smtp.starttls'))
        smtp_user = config.get('smtp.user')
        smtp_password = config.get('smtp.password')
    smtp_connection.connect(smtp_server)
    try:
        #smtp_connection.set_debuglevel(True)

        # Identify ourselves and prompt the server for supported features.
        smtp_connection.ehlo()

        # If 'smtp.starttls' is on in CKAN config, try to put the SMTP
        # connection into TLS mode.
        if smtp_starttls:
            if smtp_connection.has_extn('STARTTLS'):
                smtp_connection.starttls()
                # Re-identify ourselves over TLS connection.
                smtp_connection.ehlo()
            else:
                raise MailerException("SMTP server does not support STARTTLS")

        # If 'smtp.user' is in CKAN config, try to login to SMTP server.
        if smtp_user:
            assert smtp_password, ("If smtp.user is configured then "
                    "smtp.password must be configured as well.")
            smtp_connection.login(smtp_user, smtp_password)

        smtp_connection.sendmail(mail_from, [recipient_email], msg.as_string())
        log.info(f"Sent email to {recipient_email}")

    except smtplib.SMTPException as e:
        msg = '%r' % e
        log.exception(msg)
        raise MailerException(msg)
    finally:
        smtp_connection.quit()


def mail_recipient(recipient_name, recipient_email, subject,
        body, headers={}, role=None):
    if role is not None:
        return _mail_recipient(recipient_name, recipient_email,
            g.site_title, g.site_url, subject, body, headers=headers, role=role)
    return _mail_recipient(recipient_name, recipient_email,
            g.site_title, g.site_url, subject, body, headers=headers)


def mail_user(recipient, subject, body, headers={}, role=None):
    if (recipient.email is None) or not len(recipient.email):
        raise MailerException(_("No recipient email address available!"))
    name = recipient.display_name

    mail_recipient(name, recipient.email, subject,
            body, headers=headers, role=role)
