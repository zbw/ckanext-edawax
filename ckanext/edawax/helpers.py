import ckan.plugins.toolkit as tk
import ckan.model as model
from ckan.common import c
import ckanext.dara.helpers as dara_helpers

# decorator might useful for future
# def type_check(t):
#   def decorator(func):
#       def wrapper(*args):
#           if isinstance(args[0], t):
#               return func(*args)
#           return False
#       return wrapper
#   return decorator


def get_user_id():
    def context():
        return {'model': model, 'session': model.Session,
                'user': c.user or c.author, 'for_view': True,
                'auth_user_obj': c.userobj}
    user = tk.c.user
    if not user:
        return
    converter = tk.get_converter('convert_user_name_or_id_to_id')
    return converter(tk.c.user, context())


def show_review_button(pkg):
    return get_user_id() == pkg['creator_user_id'] and in_review(pkg) == 'false'


def in_review(pkg):
    if not isinstance(pkg, dict):
        return 'false'
    return pkg.get('dara_edawax_review', 'false')


def is_private(pkg):
    if not isinstance(pkg, dict):
        return True
    return pkg.get('private', True)


def show_publish_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return dara_helpers.check_journal_role(pkg, 'admin') and pkg.get('private', True)


def show_retract_button(pkg):
    if not isinstance(pkg, dict):
        return False
    return dara_helpers.check_journal_role(pkg, 'admin') and not pkg.get('private', True)



