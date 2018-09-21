import smtplib
from email.header import Header
from email import Utils
from email.mime.text import MIMEText
from time import time
from pylons import config
import logging
import ckan.plugins.toolkit as tk
from ckan import __version__ as ckan_version


log = logging.getLogger(__name__)


def sendmail(address, msg):
    mail_from = config.get('smtp.mail_from')
    try:
        smtp_server = config.get('smtp.test_server', config.get('smtp.server'))
        smtp_connection = smtplib.SMTP(smtp_server)
        smtp_connection.sendmail(mail_from, [address], msg.as_string())
        log.info("Sent notification to {0}".format(address))
        smtp_connection.quit()
        return True
    except Exception as e:
        log.error("Mail to {} could not be sent".format(address))
        log.error(e)
        # raise Exception  # TODO raise more detailed exception
        return False


def package_url(dataset):
    return u"{}{}".format(config.get('ckan.site_url'),
                          tk.url_for(controller='package', action='read',
                          id=dataset))

def review(addresses, author, dataset):
    """
    notify admins on new or modified entities in their organization
    """

    def subid():
        pkg = tk.get_action('package_show')(None, {'id': dataset})
        submission_id = pkg.get('dara_jda_submission_id', None)
        if submission_id:
            return u"Article Submission ID: {}\n".format(submission_id)
        return u""

    def message(address):

        body = """
Dear Editor,

the author {user} has uploaded replication files to your journal's data archive.\n

{submission_id}

You can review it here:\n\n\t {url}

best regards from ZBW--Journal Data Archive

"""
        d = {'user': author, 'url': package_url(dataset),
             'submission_id': subid()}
        body = body.format(**d)
        msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
        msg['Subject'] = Header(u"ZBW Journal Data Archive: Review Notification")
        msg['From'] = config.get('smtp.mail_from')
        msg['To'] = Header(address, 'utf-8')
        msg['Date'] = Utils.formatdate(time())
        msg['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)
        return msg

    t = map(lambda a: sendmail(a, message(a)), addresses)

    # success if we have at least one successful send
    return any(t)


def reauthor(dataset, author_mail, msg, context):
    """
    notify author that dataset should be revised
    """

    body = u"""
Dear Author,

the Editors of '{journal}' have requested that you revise the replication files
named '{title}' which you submitted to the ZBW--Journal Data Archive.

URL: {url}

{message}
"""

    def create_message():
        if msg:
            return u"Message: \n========\n\n{}".format(msg)
        return u""

    pkg = tk.get_action('package_show')(context, {'id': dataset})
    org_id = pkg.get('owner_org', pkg.get('group_id', False))
    org = tk.get_action('organization_show')(context, {'id': org_id})
    d = {'journal': org['title'], 'url': package_url(dataset), 'title': pkg.get('name'),
         'message': create_message()}
    body = body.format(**d)
    message = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    message['Subject'] = Header(u"ZBW Journal Data Archive: Please revise your uploaded dataset")
    message['From'] = config.get('smtp.mail_from')
    message['To'] = Header(author_mail, 'utf-8')
    message['Date'] = Utils.formatdate(time())
    message['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)

    return sendmail(author_mail, message)  # boolean
