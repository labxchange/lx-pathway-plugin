"""
REST API for working with LabXchange Pathways
"""
import functools

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied


User = get_user_model()

# Views


def authorized_users_only(func):
    """
    Apply a very simple permissions scheme: only usernames listed in
        LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES
    can use this API endpoint.
    """
    @functools.wraps(func)
    def api_method(_self, request, *args, **kwargs):
        if request.user.username not in settings.LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES:
            raise PermissionDenied
        return func(_self, request, *args, **kwargs)
    return api_method


