# Hendrik Bunke
# ZBW - Leibniz Information Centre for Economics

from ckan.controllers.package import PackageController
import ckan.plugins.toolkit as tk
from ckan.common import c, request, _, response
from ckan import model
import ckan.lib.helpers as h
import logging
from ckan.authz import get_group_or_org_admin_ids
from ckanext.dara.helpers import check_journal_role
from functools import wraps
import notifications as n
from ckanext.edawax.helpers import is_private
from pylons import config

# for download all
import os
import time
import zipfile
import requests
import StringIO


log = logging.getLogger(__name__)


def admin_req(func):
    @wraps(func)
    def check(*args, **kwargs):
        id = kwargs['id']
        controller = args[0]
        pkg = tk.get_action('package_show')(None, {'id': id})
        if not check_journal_role(pkg, 'admin') and not h.check_access('sysadmin'):
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

    def review(self, id):
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
        admins = get_group_or_org_admin_ids(c.pkg_dict['owner_org'])
        addresses = map(lambda admin_id: model.User.get(admin_id).email, admins)
        note = n.review(addresses, user_name, id)

        if note:
            c.pkg_dict['dara_edawax_review'] = 'true'
            tk.get_action('package_update')(context, c.pkg_dict)
            h.flash_success('Notification to Editors sent.')
        else:
            h.flash_error('ERROR: Mail could not be sent. Please try again later or contact the site admin.')

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
        set dataset private and back to review state
        """
        context = self._context()
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})

        if c.pkg_dict.get('dara_DOI_Test', False) and not h.check_access('sysadmin'):
            h.flash_error("ERROR: DOI (Test) already assigned, dataset can't be retracted")
            redirect(id)

        if c.pkg_dict.get('dara_DOI', False):
            h.flash_error("ERROR: DOI already assigned, dataset can't be retracted")
            redirect(id)

        c.pkg_dict.update({'private': True, 'dara_edawax_review': 'true'})
        tk.get_action('package_update')(context, c.pkg_dict)
        h.flash_success('Dataset retracted')
        redirect(id)

    @admin_req
    def reauthor(self, id):
        """reset dataset to private and leave review state.
        Should also send email to author
        """
        context = self._context()
        msg = tk.request.params.get('msg', '')
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        creator_mail = model.User.get(c.pkg_dict['creator_user_id']).email
        note = n.reauthor(id, creator_mail, msg, context)

        if note:
            c.pkg_dict.update({'private': True,
                               'dara_edawax_review': 'reauthor'})
            tk.get_action('package_update')(context, c.pkg_dict)
            h.flash_success('Notification sent. Dataset can now be re-edited by author')
        else:
            h.flash_error('ERROR: Mail could not be sent. Please try again later or contact the site admin.')
        redirect(id)


    def download_all(self, id):
        data = {}
        context = self._context()
        c.pkg_dict = tk.get_action('package_show')(context, {'id': id})
        zip_sub_dir = 'resources'
        zip_name = u"{}_resouces_{}.zip".format(c.pkg_dict['title'].replace(' ', '_'), time.time())

        resources = c.pkg_dict['resources']
        for resource in resources:
            rsc = tk.get_action('resource_show')(context, {'id': resource['id']})
            if rsc.get('url_type') == 'upload':
                url = resource['url']
                filename = os.path.basename(url)
                r = requests.get(url, stream=True)
                if r.status_code != 200:
                    h.flash_error('Failed to download files.')
                    redirect(id)
                else:
                    data[filename] = r

        if len(data) > 0:
            s = StringIO.StringIO()
            zf = zipfile.ZipFile(s, "w")
            for item, content in data.items():
                zip_path = os.path.join(zip_sub_dir, item)
                zf.writestr(zip_path, content.content)
            zf.close()
            response.headers.update({"Content-Disposition": "attachment;filename={}".format(zip_name.encode('utf8'))})
            response.content_type = "application/zip"
            return s.getvalue()
        # if there's nothing to download but someone gets to the download page
        # /download_all, return them to the landing page
        h.flash_error('Nothing to download.')
        redirect(id)





def redirect(id):
    tk.redirect_to(controller='package', action='read', id=id)


class InfoController(tk.BaseController):

    TEMPLATE = "info_index.html"

    def index(self):
        return tk.render(self.TEMPLATE, extra_vars={'page': 'index'})

    def md_page(self):
        plist = tk.request.path.rsplit('/', 1)
        return tk.render(self.TEMPLATE, extra_vars={'page': plist[-1]})
