"""
REST API for working with LabXchange Pathways
"""
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.http import HttpResponse, Http404
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey
from opaque_keys.edx.locator import CourseLocator
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from openedx.core.lib.api.view_utils import view_auth_classes

from lx_pathway_plugin.keys import PathwayLocator
from lx_pathway_plugin.models import Pathway, PathwaySerializer

# Views


@view_auth_classes()
class PathwayView(APIView):
    """
    Main API view for working with a specific pathway
    """
    def get(self, request, pathway_key_str):
        """
        Get a pathway
        """
        try:
            pathway_key = PathwayLocator.from_string(pathway_key_str)
            pathway = Pathway.objects.get(uuid=pathway_key.uuid)
        except (InvalidKeyError, Pathway.DoesNotExist):
            raise Http404
        # TODO: add permissions
        return Response(PathwaySerializer(pathway).data)


@api_view(['POST'])
@view_auth_classes()
def create_pathway(request):
    """
    Create a pathway
    """
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
