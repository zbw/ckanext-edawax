import smtplib
from pylons import config
from email.header import Header
from email import Utils
import ckan
from email.mime.text import MIMEText
import logging
from time import time
import ckan.plugins.toolkit as tk

log = logging.getLogger(__name__)


def notification(to, author, entity, operation):
    """
    notify admins on new or modified entities in their organization
    """
    
    body = """
Dear Editor,

the EDaWaX user {user} has {operation} a dataset in your journal's data
archive. You can review it here:\n\n\t {url}

best regards from EDaWaX
"""
    url = u"{}{}".format(config.get('ckan.site_url'),
                         tk.url_for(controller='package', action='read',
                         id=entity))
    
    d = {'user': author, 'operation': operation, 'url': url}
    body = body.format(**d)
    mail_from = config.get('smtp.mail_from')
    msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    msg['Subject'] = Header(u"EDaWaX Notification")
    msg['From'] = mail_from
    msg['To'] = Header(to, 'utf-8')
    msg['Date'] = Utils.formatdate(time())
    msg['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan.__version__)
    
    # for now just try to send an email. If that fails pass and go on
    # TODO: log entry, raise error, check for smtp.test_server TODO
    try:
        smtp_server = config['smtp.server']
        smtp_connection = smtplib.SMTP(smtp_server)
        smtp_connection.sendmail(mail_from, [to], msg.as_string())
        log.info("Sent email to {0}".format(to))
        smtp_connection.quit()
    except:
        pass



    
    

