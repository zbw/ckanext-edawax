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
from ckanext.dara import helpers as dara_helpers
from functools import wraps


log = logging.getLogger(__name__)


def admin_req(func):
    @wraps(func)
    def check(*args, **kwargs):
        id = kwargs['id']
        controller = args[0]
        pkg = tk.get_action('package_show')(None, {'id': id})
        if not dara_helpers.check_journal_role(pkg, 'admin') and not h.check_access('sysadmin'):
            tk.abort(403, 'Unauthorized')
        return func(controller, id)
    return check


class WorkflowController(PackageController):
    """
    """

    def _context(self):
        return {'model': model, 'session': model.Session,
                'user': c.user or c.author, 'for_view': True,
                'auth_user_obj': c.userobj}

    def review_mail(self, id):
        """
        sends review notification to all journal admins
        """
        
        context = self._context()
        
        try:
            tk.check_access('package_update', context, {'id': id})
        except tk.NotAuthorized:
            tk.abort(403, 'Unauthorized')

        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        
        # avoid multiple notifications (eg. when someone calls review directly)
        if c.pkg_dict.get('dara_edawax_review', 'false') == 'true':
            h.flash_error("Package has already been sent to review")
            redirect(id)
        
        user_name = tk.c.userobj.fullname or tk.c.userobj.email
        org_admins = get_group_or_org_admin_ids(c.pkg_dict['owner_org'])
        addresses = map(lambda admin_id: model.User.get(admin_id).email, org_admins)
        note = notification(addresses, user_name, id)
        
        if note:
            c.pkg_dict['dara_edawax_review'] = True
            tk.get_action('package_update')(context, c.pkg_dict)
            h.flash_success('Notification to Editors sent.')
        else:
            h.flash_error('ERROR: Mail could not be sent. Please try again\
                    later or contact the {}\
                    admin.'.format(config.get('ckan.site_title', '')))

        redirect(id)

    @admin_req
    def publish(self, id):
        """
        publish dataset
        """
        context = self._context()
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        c.pkg_dict.update({'private': False, 'dara_edawax_review': 'reviewed'})
        tk.get_action('package_update')(context, c.pkg_dict)
        h.flash_success('Dataset published')
        redirect(id)

    @admin_req
    def retract(self, id):
        """
        set dataset private
        """
        context = self._context()
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        c.pkg_dict.update({'private': True})
        tk.get_action('package_update')(context, c.pkg_dict)
        h.flash_success('Dataset set private')
        redirect(id)


def redirect(id):
        tk.redirect_to(controller='package', action='read', id=id)


def notification(addresses, author, dataset):
    """
    notify admins on new or modified entities in their organization
    """
    
    mail_from = config.get('smtp.mail_from')
    
    def message(address):
        
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
        msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
        msg['Subject'] = Header(u"EDaWaX Notification")
        msg['From'] = mail_from
        msg['To'] = Header(address, 'utf-8')
        msg['Date'] = Utils.formatdate(time())
        msg['X-Mailer'] = "CKAN {} [Plugin edawax]".format(ckan.__version__)
        return msg
        
    def send(address, msg):
        try:
            smtp_server = config.get('smtp.test_server', config.get('smtp.server'))
            smtp_connection = smtplib.SMTP(smtp_server)
            smtp_connection.sendmail(mail_from, [address], msg.as_string())
            log.info("Sent review notification to {0}".format(address))
            smtp_connection.quit()
            return True
        except:
            log.error("Mail to {} could not be sent".format(address))
            # raise Exception  # TODO raise more detailed exception with error description
            return False

    t = map(lambda a: send(a, message(a)), addresses)
    
    # success if we have at least one successful send
    if True in t:
        return True
    return False

    


