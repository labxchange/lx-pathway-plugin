"""
REST API for working with LabXchange Pathways
"""
import functools

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.http import Http404
from opaque_keys import InvalidKeyError
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from lx_pathway_plugin.keys import PathwayLocator
from lx_pathway_plugin.models import Pathway, PathwaySerializer
from openedx.core.lib.api.view_utils import view_auth_classes

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


@view_auth_classes()
class PathwayView(APIView):
    """
    Main API view for working with a specific pathway
    """
    @authorized_users_only
    def get(self, request, pathway_key_str):
        """
        Get a pathway
        """
        pathway = get_pathway_or_404(pathway_key_str)
        return Response(PathwaySerializer(pathway).data)

    @authorized_users_only
    def patch(self, request, pathway_key_str):
        """
        Update a pathway's draft data.
        The body of this request must be a JSON object with only a 'draft_data'
        key, which is the new draft data for the pathway.
        """
        pathway = get_pathway_or_404(pathway_key_str)
        serializer = PathwaySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "draft_data" in data:
            pathway.draft_data = data["draft_data"]  # Will be validated and cleaned by save()
        if "owner_user_id" in data or "owner_group_name" in data:
            if not request.user.is_staff:
                raise PermissionDenied("Only global staff can change a pathway owner.")
            if data.get("owner_user_id"):
                pathway.owner_user = User.objects.get(pk=data["owner_user_id"])
                pathway.owner_group = None
            elif data.get("owner_group_name"):
                pathway.owner_user = None
                pathway.owner_group = Group.objects.get(name=data["owner_group_name"])
        pathway.save()
        return Response(PathwaySerializer(pathway).data)

    @authorized_users_only
    def delete(self, request, pathway_key_str):
        """
        Delete a pathway
        """
        pathway = get_pathway_or_404(pathway_key_str)
        pathway.delete()
        return Response({})


@view_auth_classes()
class PathwayPublishView(APIView):
    """
    Publish or revert changes to a pathway

    Note: No history is kept; only the current draft and the last published
    version.
    """
    @authorized_users_only
    def post(self, request, pathway_key_str):
        """
        Publish changes
        """
        pathway = get_pathway_or_404(pathway_key_str)
        pathway.published_data = pathway.draft_data
        pathway.save()
        return Response(PathwaySerializer(pathway).data)

    @authorized_users_only
    def delete(self, request, pathway_key_str):
        """
        Revert this pathway to the last published version
        """
        pathway = get_pathway_or_404(pathway_key_str)
        pathway.draft_data = pathway.published_data
        pathway.save()
        return Response(PathwaySerializer(pathway).data)


@api_view(['POST'])
@view_auth_classes()
def create_pathway(request):
    """
    Create a pathway
    """
    if request.user.username not in settings.LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES:
        raise PermissionDenied
    serializer = PathwaySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    kwargs = {}
    if 'owner_group_name' in serializer.validated_data:
        if request.user.is_staff:
            groups = Group.objects  # Global staff can create pathways owned by any group
        else:
            groups = request.user.groups  # Regular users can only create pathways owned by groups they belong to
        try:
            # To specify a group, the user must be a member of the group:
            group = groups.get(name=serializer.validated_data['owner_group_name'])
        except Group.DoesNotExist:
            raise ValidationError("Invalid group name. Does the group exist and are you a member?")
        kwargs['owner_group'] = group
    else:
        kwargs['owner_user'] = request.user

    if 'uuid' in serializer.validated_data:
        kwargs['uuid'] = serializer.validated_data['uuid']
    if 'draft_data' in serializer.validated_data:
        kwargs['draft_data'] = serializer.validated_data['draft_data']

    try:
        pathway = Pathway.objects.create(**kwargs)
    except IntegrityError:
        raise ValidationError("A conflicting pathway already exists.")
    return Response(PathwaySerializer(pathway).data)


def get_pathway_or_404(pathway_key_str):
    """
    Get the pathway from the given string key
    """
    try:
        pathway_key = PathwayLocator.from_string(pathway_key_str)
        return Pathway.objects.get(uuid=pathway_key.uuid)
    except (InvalidKeyError, Pathway.DoesNotExist):
        raise Http404
