"""
The included functions are an attempt to decouple the invitation system
from the core CKAN code. Additionally, it provides for a way to send
invitations based on the role of the invitee.

Role of the new user gets passed down to functions so that a decision can
be made about which template to use of the email.
"""
import ckan, random
from pylons import config
import ckan.lib.mailer as mailer
import ckan.logic.action.create as logic
from ckan.lib.base import render_jinja2

#imports for expanded mailing
import os
import smtplib
import logging
from time import time
from email import Utils
from ckan.common import _, g
from email.header import Header
import paste.deploy.converters
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


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
    extra_vars = {'reset_link': mailer.get_reset_link(user),
       'site_title': config.get('ckan.site_title'),
       'user_name': user.name,
       'site_url': config.get('ckan.site_url'),
       'journal_title': data['journal_title']}

    role = _get_user_role(user.name, data['group_id'])
    if role in ['editor', 'admin']:
        return render_jinja2('emails/invite_editor.txt', extra_vars)
    return render_jinja2('emails/invite_author.txt', extra_vars)


def send_invite(user, data):
    mailer.create_reset_key(user)
    body = get_invite_body(user, data=data)
    subject = mailer._('Invite for {site_title}').format(site_title=mailer.g.site_title)
    # pass role to mail function to check if the attachement should be sent
    role = data['role']
    mail_user(user, subject, body, {}, role)


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


# modifying CKAN's base mail function to allow sending attachments
def _mail_recipient(recipient_name, recipient_email,
        sender_name, sender_url, subject,
        body, headers={}, role=None):
    mail_from = config.get('smtp.mail_from')
    body = mailer.add_msg_niceties(recipient_name, body, sender_name, sender_url)
    msg_body = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    msg = MIMEMultipart()
    for k, v in headers.items(): msg[k] = v
    subject = Header(subject.encode('utf-8'), 'utf-8')
    msg['Subject'] = subject
    msg['From'] = _("%s <%s>") % (sender_name, mail_from)
    recipient = u"%s <%s>" % (recipient_name, recipient_email)
    msg['To'] = Header(recipient, 'utf-8')
    msg['Date'] = Utils.formatdate(time())
    msg['X-Mailer'] = "CKAN %s" % ckan.__version__

    msg.attach(msg_body)

    # attach the file
    if role is not None and role == u'member':
        attachment_file_name = "QuickManual_V1.2.3.pdf"
        directory = os.path.dirname(__file__)
        rel_path = 'public/{}'.format(attachment_file_name)
        with open(os.path.join(directory, rel_path), 'rb') as file:
            part = MIMEApplication(
                                    file.read(),
                                    name=attachment_file_name
                                  )
        part['Content-Disposition'] = 'attachment; filename={}'.format(attachment_file_name)
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
        smtp_starttls = paste.deploy.converters.asbool(
                config.get('smtp.starttls'))
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
        log.info("Sent email to {0}".format(recipient_email))

    except smtplib.SMTPException, e:
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
    mail_recipient(recipient.display_name, recipient.email, subject,
            body, headers=headers, role=role)
