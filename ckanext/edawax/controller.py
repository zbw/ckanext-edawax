# Hendrik Bunke
# ZBW - Leibniz Information Centre for Economics

from ckan.controllers.package import PackageController
import ckan.plugins.toolkit as tk
from ckan.common import c, response
from ckan import model
import ckan.lib.helpers as h
import smtplib
from pylons import config
from email.header import Header
from email import Utils
import ckan
from email.mime.text import MIMEText
import logging
from time import time
from ckan.authz import get_group_or_org_admin_ids



log = logging.getLogger(__name__)


class EdawaxController(PackageController):
    """
    """
    # TODO more functional

    def _context(self):
        return {'model': model, 'session': model.Session,
                'user': c.user or c.author, 'for_view': True,
                'auth_user_obj': c.userobj}
    
    def _check_access(self, id):
        context = self._context()
        try:
            tk.check_access('package_update', context, {'id': id})
        except tk.NotAuthorized:
            tk.abort(401, 'Unauthorized')
    
    def _redirect(self, id):
        tk.redirect_to(controller='package', action='read', id=id)

    def review_mail(self, id):
        context = self._context()
        self._check_access(id)
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        
        if c.pkg_dict['dara_edawax_status']:
            h.flash_error("Package has already been sent to review")
            self._redirect(id)

        user_id, user_name = tk.c.userobj.id, tk.c.userobj.fullname
        if not user_name:
            user_name = tk.c.userobj.email  # otherwise None

        org_admins = filter(lambda x: x != user_id,
                            get_group_or_org_admin_ids(c.pkg_dict['owner_org']))
        addresses = map(lambda admin_id: model.User.get(admin_id).email, org_admins)
        map(lambda a: notification(a, user_name, id), addresses)
        
        # set and store review status
        c.pkg_dict['dara_edawax_status'] = 'review'
        tk.get_action('package_update')(context, c.pkg_dict)
        
        # TODO alert window/dialog; jquery has dialog

        h.flash_success('Mail to Editors sent')
        self._redirect(id)
       

def notification(to, author, dataset):
    """
    notify admins on new or modified entities in their organization
    """
    
    body = """
Dear Editor,

the author {user} has uploaded a dataset to your journal's data archive.\n
You can review it here:\n\n\t {url}

best regards from EDaWaX
"""
    url = u"{}{}".format(config.get('ckan.site_url'),
                         tk.url_for(controller='package', action='read',
                         id=dataset))
    
    d = {'user': author, 'url': url}
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



