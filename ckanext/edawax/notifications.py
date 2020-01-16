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
    log.info('Sending Notifcation to: {}'.format(address))
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

subjects = {
            "review_editor": u"ZBW Journal Data Archive: Review Notification",
            "review_reviewer": u"ZBW Journal Data Archive: Review Notification",
            "author": u"ZBW Journal Data Archive - Dataset Status Change",
            "editor": u"ZBW Journal Data Archive: Review Completed",
            "reauthor": u"ZBW Journal Data Archive: Please revise your uploaded dataset",
           }

msg_body = {
            "review_editor": u"""
Dear Editor,

The author, {user}, has uploaded replication files, "{title}," to the data archive for your journal, the "{journal}."

You can review it here: {url}

{submission_id}

best regards from ZBW--Journal Data Archive
""",
            "review_reviewer": u"""
Dear Reviewer,

Replication files, "{title}," have been added to the "{journal}" and are are ready for review.

You can review them here: {url}

{submission_id}

best regards from ZBW--Journal Data Archive
""",
            "author": u"""
Dear Author,

Your submission, "{title}," to "{journal}" has been {status}. It is available here: {url}.

{message}

best regards from ZBW--Journal Data Archive
""",
            "editor": u"""
Dear Editor,

A reviewer has finished reviewing "{title}" in your journal, the "{journal}." The submission is available here: {url}.

{message}
""",
            "reauthor": u"""
Dear Author,

The Editors of the "{journal}" have requested that you revise your replication files "{title}" which you submitted to the ZBW--Journal Data Archive.

URL: {url}

{message}

best regards from ZBW--Journal Data Archive
""",
           }

def create_message(msg):
    if msg:
        return u"Message: \n========\n\n{}".format(msg)
    return u""


def compose_message(typ, body, subject, config, send_to, context=None):
    # used by editor and reauthor
    reviewer_email = tk.get_action('user_show')(context, {'id': c.user})['email']

    msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    msg['Subject'] = Header(subject)
    if typ in ['editor', 'reauthor']:
        msg['From'] = reviewer_email
    else:
        msg['From'] = config.get('smtp.mail_from')
    msg['To'] = Header(send_to, 'utf-8')
    msg['Date'] = Utils.formatdate(time())
    msg['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)
    return msg


def notify(typ, dataset, author_mail, msg, context, status=None):
    log.info('Notifing {}'.format(typ))
    context['ignore_auth'] = True
    body = msg_body[typ]
    pkg = tk.get_action('package_show')(context, {'id': dataset})
    org_id = pkg.get('owner_org', pkg.get('group_id', False))
    org = tk.get_action('organization_show')(context, {'id': org_id})
    # if typ is "author" needs status
    d = {'journal': org['title'],
         'url': package_url(dataset),
         'title': pkg.get('title').title(),
         'message': create_message(msg)}
    if status:
        d['status'] = status
    body = body.format(**d)
    subject = subjects[typ]
    message = compose_message(typ, body, subject, config, author_mail, context)
    return sendmail(author_mail, message)


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

    def message(who, address):
        body = msg_body[who]
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
        subject = subjects[who]
        return compose_message(who, body, subject, config, address)
    # send email
    # to Admin
    t = []
    if pkg_status(dataset) in ['reauthor', 'false', 'reviewers'] \
        or reviewers == [None, None]:
        t = map(lambda a: sendmail(a, message("review_editor", a)), addresses)
    else:
        # To Reviewer
        if reviewers is not None:
            for reviewer in reviewers:
                if reviewer is not None:
                    t.append(sendmail(reviewer, message("review_reviewer", reviewer)))

    # success if we have at least one successful send
    return any(t)
