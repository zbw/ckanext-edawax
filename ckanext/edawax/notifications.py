import smtplib
from email.header import Header
from email import utils
from email.mime.text import MIMEText
from time import time
from ckan.common import config, g
import logging
import ckan.plugins.toolkit as tk
from ckan import __version__ as ckan_version
from ckanext.edawax.helpers import pkg_status
import ckan.lib.mailer as mailer

log = logging.getLogger(__name__)


def sendmail(address, msg):
    log.info(f'Sending Notifcation to: {address}')
    mail_from = config.get('smtp.mail_from')
    try:
        smtp_server = config.get('smtp.test_server', config.get('smtp.server'))
        smtp_connection = smtplib.SMTP(smtp_server)
        smtp_connection.sendmail(mail_from, [address], msg.as_string())
        log.info(f"Sent notification to {address}")
        smtp_connection.quit()
        return True
    except Exception as e:
        log.error(f"Mail to {address} could not be sent")
        log.error(f"{e}")
        return False


def package_url(dataset):
    site_url = config.get('ckan.site_url')
    url = tk.url_for('dataset.read', id=dataset)
    return f"{site_url}{url}"

subjects = {
            "review_editor": u": Data Submission Notification",
            "review_reviewer": u": Review Request",
            "author": u": Dataset Status Change",
            "editor": u": Review Completed",
            "reauthor": u": Please revise your uploaded dataset",
           }

msg_body = {
            "review_editor": (
                u"Dear Editor,\n\n",
                u"the author, {user}, has uploaded replication files,",
                u" \"{title},\" to the data archive for your journal, the \"{journal}.\"",
                u"\n\nYou can review them here: {url}",
                u"\n{submission_id}",
                u"\n\nKind regards,\nZBW Journal Data Archive",
            ),
            "review_reviewer": (
                u"Dear Reviewer ({reviewer_name}),\n\n",
                u"the editorial office would like you to review\n",
                u"\"{title},\" in the \"{journal}\".",
                u"\n\nYou can review it here: {url}",
                u"\n{submission_id}",
                u"\n\nKind regards,\nZBW Journal Data Archive",
            ),
            "author": (
                u"Dear Author,\n\n",
                u"your submission, \"{title},\" to \"{journal}\" has been",
                u" {status}. It is available here: {url}.",
                u"\n\n{message}",
                u"\n\nKind regards,\nZBW Journal Data Archive",
            ),
            "editor": (
                u"Dear Editor,\n\n",
                u"a reviewer has finished reviewing \"{title}\" in your journal,",
                u" the \"{journal}.\" The submission is available here: {url}.",
                u"\n\n{message}",
                u"\nKind regards,\nZBW Journal Data Archive"
            ),
            "reauthor": (
                u"Dear Author,\n",
                u"\nthe Editors of the \"{journal}\" have requested ",
                u"that you revise your replication files \"{title}\""
                u" which you submitted to the ZBW Journal Data Archive.\n",
                u"\nURL: {url}\n",
                u"\n{message}\n",
                u"\nKind regards,\nZBW Journal Data Archive"
            ),
            "reviewer_message": (
                u"Dear Reviewer,\n\n",
                u"the editor of \"{journal}\" would like you to ",
                u"relook at the replications files for \"{title}.\"",
                u"\n{message}\n",
                u"\n\nYou can review them here: {url}",
                u"\n{submission_id}",
                u"\n\nKind regards,\nZBW Journal Data Archive",
            )
           }


def create_message(msg):
    if msg:
        return f"Message: \n========\n{msg}\n"
    return u""


def compose_message(typ, body, subject, config, send_to, context=None):
    # used by editor and reauthor
    reviewer_email = tk.get_action('user_show')(context, {'id': g.user})['email']

    msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    msg['Subject'] = Header(subject)
    msg['From'] = config.get('smtp.mail_from')
    if typ in ['editor', 'reauthor']:
        msg['Cc'] = reviewer_email
    msg['To'] = Header(send_to, 'utf-8')
    msg['Date'] = utils.formatdate(time())
    msg['X-Mailer'] = f"CKAN {ckan_version} [Plugin edawax]"

    return msg


def notify(typ, dataset, author_mail, msg, context, status=None):
    context['ignore_auth'] = True
    body = "".join(msg_body[typ])
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
    site_title = config.get('ckan.site_title')
    sub = subjects[typ]
    subject = f'{site_title}{sub}'
    message = compose_message(typ, body, subject, config, author_mail, context)

    return sendmail(author_mail, message)


def review(addresses, author, dataset, reviewers=None, msg=None):
    """
    notify admins on new or modified entities in their organization
    """
    def subid():
        pkg = tk.get_action('package_show')(None, {'id': dataset})
        submission_id = pkg.get('dara_jda_submission_id', None)
        if submission_id:
            return f"Article Submission ID: {submission_id}\n"
        return u""

    def message(who, address):
        body = "".join(msg_body[who])
        context = {}
        context['ignore_auth'] = True
        pkg = tk.get_action('package_show')(context, {'id': dataset})
        org_id = pkg.get('owner_org', pkg.get('group_id', False))
        org = tk.get_action('organization_show')(context, {'id': org_id})
        if pkg['maintainer'] and '/' in pkg['maintainer']:
            _, reviewer_name = pkg['maintainer'].split('/')
        else:
            reviewer_name = ''
        d = {'user': author,
             'url': package_url(dataset),
             'submission_id': subid(),
             'title': pkg.get('title').title(),
             'journal': org['title'],
             'reviewer_name': reviewer_name}
        if msg:
            d['message'] = create_message(msg)
        body = body.format(**d)
        site_title = config.get('ckan.site_title')
        sub = subjects[who]
        subject = f'{site_title}{sub}'
        return compose_message(who, body, subject, config, address)

    # send email to Admin
    t = []
    if pkg_status(dataset) in ['false', 'reauthor'] or reviewers == [None, None]:
        t = list(map(lambda a: sendmail(a, message("review_editor", a)), addresses))
    else:
        # To Reviewer
        if reviewers is not None:
            for reviewer in reviewers:
                if reviewer not in [None, '', u'']:
                    t.append(sendmail(reviewer.split('/')[0], message("review_reviewer", reviewer.split('/')[0])))
        else:
            # want to return something so that there's no error message
            # previously, this condition would have triggered an email to the editors
            t.append(True)

    # success if we have at least one successful send
    return any(t)
