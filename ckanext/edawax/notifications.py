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
        log.error("{} {} {}".format(e, e.message, e.args))
        # raise Exception  # TODO raise more detailed exception
        return False


def package_url(dataset):
    return u"{}{}".format(config.get('ckan.site_url'),
                          tk.url_for(controller='package', action='read',
                          id=dataset))

subjects = {
            "review_editor": u"ZBW Journal Data Archive: Data Submission Notification",
            "review_reviewer": u"ZBW Journal Data Archive: Data Submission Notification",
            "author": u"ZBW Journal Data Archive: Dataset Status Change",
            "editor": u"ZBW Journal Data Archive: Review Completed",
            "reauthor": u"ZBW Journal Data Archive: Please revise your uploaded dataset",
           }

msg_body = {
            "review_editor": (
                u"Dear Editor,\n\n",
                u"The author, {user}, has uploaded replication files,",
                u" \"{title},\" to the data archive for your journal, the \"{journal}.\"",
                u"\n\nYou can review them here: {url}",
                u"\n{submission_id}",
                u"\n\nKind regards,\nZBW Journal Data Archive",
            ),
            "review_reviewer": (
                u"Dear Reviewer,\n\n",
                u"Replication files, \"{title},\" have been added to the",
                u" \"{journal}\" and are ready for review.",
                u"\n\nYou can review them here: {url}",
                u"\n{submission_id}",
                u"\n\nKind regards,\nZBW Journal Data Archive",
            ),
            "author": (
                u"Dear Author,\n\n",
                u"Your submission, \"{title},\" to \"{journal}\" has been",
                u" {status}. It is available here: {url}.",
                u"\n\n{message}",
                u"\n\nKind regards,\nZBW Journal Data Archive",
            ),
            "editor": (
                u"Dear Editor,\n\n",
                u"A reviewer has finished reviewing \"{title}\" in your journal,",
                u" the \"{journal}.\" The submission is available here: {url}.",
                u"\n\n{message}",
            ),
            "reauthor": (
                u"Dear Author,\n",
                u"\nThe Editors of the \"{journal}\" have requested ",
                u"that you revise your replication files \"{title}\""
                u" which you submitted to the ZBW Journal Data Archive.\n",
                u"\nURL: {url}\n",
                u"\n{message}\n",
                u"\nKind regards,\nZBW Journal Data Archive"
            ),
            "reviewer_message": (
                u"Dear Reviewer,\n\n",
                u"The editor of \"{journal}\" would like you to ",
                u"relook at the replications files for \"{title}.\"",
                u"\n{message}\n",
                u"\n\nYou can review them here: {url}",
                u"\n{submission_id}",
                u"\n\nKind regards,\nZBW Journal Data Archive",
            )
           }


def create_message(msg):
    if msg:
        return u"Message: \n========\n{}".format(msg)
    return u""


def compose_message(typ, body, subject, config, send_to, context=None):
    # used by editor and reauthor
    reviewer_email = tk.get_action('user_show')(context, {'id': c.user})['email']

    msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    msg['Subject'] = Header(subject)
    msg['From'] = config.get('smtp.mail_from')
    if typ in ['editor', 'reauthor']:
        msg['Cc'] = reviewer_email
    msg['To'] = Header(send_to, 'utf-8')
    msg['Date'] = Utils.formatdate(time())
    msg['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan_version)

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
    subject = subjects[typ]
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
            return u"Article Submission ID: {}\n".format(submission_id)
        return u""

    def message(who, address):
        body = "".join(msg_body[who])
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
        if msg:
            d['message'] = create_message(msg)
        body = body.format(**d)
        subject = subjects[who]
        return compose_message(who, body, subject, config, address)

    # send email to Admin
    # this should never happen, because if there are no reviewers, there's no button
    t = []
    if reviewers == [None, None]:
        # pkg_status(dataset) in ['reauthor', 'false', 'reviewers', 'editor']
        t = map(lambda a: sendmail(a, message("review_editor", a)), addresses)
    else:
        if pkg_status(dataset) not in ['reauthor', 'false', 'reviewers', 'editor']:
            # To Reviewer
            if reviewers is not None:
                for reviewer in reviewers:
                    if reviewer not in [None, '', u'']:
                        t.append(sendmail(reviewer, message("review_reviewer", reviewer)))

    # success if we have at least one successful send
    return any(t)
