import smtplib
from email.header import Header
from email import Utils
from email.mime.text import MIMEText
from time import time
from pylons import config, c
import logging
import ckan.plugins.toolkit as tk
from ckan import __version__ as ckan_version
from ckanext.edawax.helpers import pkg_status

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

def review(addresses, author, dataset, reviewers=None):
    """
    notify admins on new or modified entities in their organization
    """
    def subid():
        pkg = tk.get_action('package_show')(None, {'id': dataset})
        submission_id = pkg.get('dara_jda_submission_id', None)
        if submission_id:
            return u"Article Submission ID: {}\n".format(submission_id)
        return u""

    def message_editor(address):

        body = u"""
Dear Editor,

The author, {user}, has uploaded replication files, "{title}," to the data archive for your journal, the "{journal}."

You can review it here: {url}

{submission_id}

best regards from ZBW--Journal Data Archive

"""
        context = {}
        context['ignore_auth'] = True
        pkg = tk.get_action('package_show')(context, {'id': dataset})
        org_id = pkg.get('owner_org', pkg.get('group_id', False))
        org = tk.get_action('organization_show')(context, {'id': org_id})
        d = {'user': author,
             'url': package_url(dataset),
             'submission_id': subid(),
             'title': pkg.get('title').title(),
             'journal': org['title']}
        body = body.format(**d)
        msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
        msg['Subject'] = Header(u"ZBW Journal Data Archive: Review Notification")
        msg['From'] = config.get('smtp.mail_from')
        msg['To'] = Header(address, 'utf-8')
        msg['Date'] = Utils.formatdate(time())
        msg['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)
        return msg

    def message_reviewer(address):

        body = u"""
Dear Reviewer,

Replication files, "{title}," have been added to the "{journal}" and are are ready for review.

You can review them here: {url}

{submission_id}

best regards from ZBW--Journal Data Archive

"""
        context = {}
        context['ignore_auth'] = True
        pkg = tk.get_action('package_show')(context, {'id': dataset})
        org_id = pkg.get('owner_org', pkg.get('group_id', False))
        org = tk.get_action('organization_show')(context, {'id': org_id})
        d = {'user': author,
             'url': package_url(dataset),
             'submission_id': subid(),
             'title': pkg.get('title').title(),
             'journal': org['title']}
        body = body.format(**d)
        msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
        msg['Subject'] = Header(u"ZBW Journal Data Archive: Review Notification")
        msg['From'] = config.get('smtp.mail_from')
        msg['To'] = Header(address, 'utf-8')
        msg['Date'] = Utils.formatdate(time())
        msg['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)
        return msg

    # send email
    # to Admin
    t = []
    if pkg_status(dataset) in ['reauthor', 'false', 'reviewers'] \
        or reviewers == [None, None]:
        t = map(lambda a: sendmail(a, message_editor(a)), addresses)
    else:
        # To Reviewer
        if reviewers is not None:
            for reviewer in reviewers:
                if reviewer is not None:
                    t.append(sendmail(reviewer, message_reviewer(reviewer)))

    # success if we have at least one successful send
    return any(t)


def author_notify(dataset, author_mail, msg, context, status):
    """
    Notify the author that one of there submission has been published,
    or that one has been retracted.
    """
    body = u"""
Dear Author,

Your submission, "{title}," to "{journal}" has been {status}. It is available here: {url}.

{message}

best regards from ZBW--Journal Data Archive
            """

    def create_messate():
        if msg:
            return u"Message: \n==========\n\n{}".format(msg)
        return u""

    context['ignore_auth'] = True
    pkg = tk.get_action('package_show')(context, {'id': dataset})
    org_id = pkg.get('owner_org', pkg.get('group_id', False))
    org = tk.get_action('organization_show')(context, {'id': org_id})
    d = {'journal': org['title'],
         'url': package_url(dataset),
         'title': pkg.get('title').title(),
         'status': status,
         'message': create_messate()}
    body = body.format(**d)
    message = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    message['Subject'] = Header(u'ZBW Journal Data Archive - Dataset Status Change')
    message['From'] = config.get('smtp.mail_from')
    message['To'] = Header(author_mail, 'utf-8')
    message['Date'] = Utils.formatdate(time())
    message['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)

    return sendmail(author_mail, message)


def editor_notify(dataset, author_mail, msg, context):
    """
    Notify journal editor that the review is finished
    """
    body = u"""
Dear Editor,

A reviewer has finished reviewing "{title}" in your journal, the "{journal}." The submission is available here: {url}.

{message}
    """

    def create_message():
        if msg:
            return u"Message: \n========\n\n{}".format(msg)
        return u""

    reviewer_email = tk.get_action('user_show')(context, {'id': c.user})['email']

    context['ignore_auth'] = True
    pkg = tk.get_action('package_show')(context, {'id': dataset})
    org_id = pkg.get('owner_org', pkg.get('group_id', False))
    org = tk.get_action('organization_show')(context, {'id': org_id})
    d = {'journal': org['title'],
         'url': package_url(dataset),
         'title': pkg.get('title').title(),
         'message': create_message()}
    body = body.format(**d)
    message = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    message['Subject'] = Header(u"ZBW Journal Data Archive: Review Completed")
    message['From'] = reviewer_email
    message['To'] = Header(author_mail, 'utf-8')
    message['Cc'] = config.get('smtp.mail_from')
    message['Date'] = Utils.formatdate(time())
    message['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)

    return sendmail(author_mail, message)  # boolean



def reauthor(dataset, author_mail, msg, context):
    """
    notify author that dataset should be revised
    """

    body = u"""
Dear Author,

The Editors of the "{journal}" have requested that you revise your replication files "{title}" which you submitted to the ZBW--Journal Data Archive.

URL: {url}

{message}

best regards from ZBW--Journal Data Archive
"""

    def create_message():
        if msg:
            return u"Message: \n========\n\n{}".format(msg)
        return u""

    reviewer_email = tk.get_action('user_show')(context, {'id': c.user})['email']

    pkg = tk.get_action('package_show')(context, {'id': dataset})
    org_id = pkg.get('owner_org', pkg.get('group_id', False))
    org = tk.get_action('organization_show')(context, {'id': org_id})
    d = {'journal': org['title'],
         'url': package_url(dataset),
         'title': pkg.get('title'),
         'message': create_message()}
    body = body.format(**d)
    message = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    message['Subject'] = Header(u"ZBW Journal Data Archive: Please revise your uploaded dataset")
    message['From'] = reviewer_email
    message['To'] = Header(author_mail, 'utf-8')
    message['Cc'] = config.get('smtp.mail_from')
    message['Date'] = Utils.formatdate(time())
    message['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)

    return sendmail(author_mail, message)  # boolean
