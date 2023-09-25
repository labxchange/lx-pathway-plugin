"""
Django models for the pathways plugin.
"""
# pylint: disable=abstract-method
import random
from logging import getLogger

from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import UsageKey
from rest_framework import serializers

from .keys import PathwayLocator, PathwayUsageLocator

log = getLogger(__name__)
User = get_user_model()



# Serializers


def make_random_id():
    """
    Generate a short, random string that's likely to be unique within the
    pathway. Pathways are capped at 100 items, so we don't have to work too hard
    to ensure this is unique.
    """
    return ''.join(random.SystemRandom().choice('0123456789abcdef') for n in range(8))


class PathwayItemSerializer(serializers.Serializer):
    """
    Serializer for the data about each item in a pathway
    """
    # The XBlock's usage key in this pathway:
    usage_id = serializers.SerializerMethodField(required=False, read_only=True)
    original_usage_id = serializers.CharField()  # The XBlock's original usage key (in a library, course, or pathway)
    id = serializers.SlugField(default=make_random_id)
    data = serializers.JSONField(default={})  # Other arbitrary data like "notes"

    def get_usage_id(self, obj):
        """
        Get the pathway-specific usage key of this block.
        """
        if "pathway" in self.context:
            pathway_key = PathwayLocator(uuid=self.context["pathway"].uuid)
            block_type = UsageKey.from_string(obj["original_usage_id"]).block_type
            usage_id = obj["id"]
            return str(PathwayUsageLocator(pathway_key=pathway_key, block_type=block_type, usage_id=usage_id))

    def validate_original_usage_id(self, obj):
        """
        Validates the original_usage_id field isn't from a pathway child (it should be from an original asset)
        """
        locator = UsageKey.from_string(obj)
        if isinstance(locator, PathwayUsageLocator):
            raise serializers.ValidationError("Invalid asset key")
        return obj


class PathwayDataSerializer(serializers.Serializer):
    """
    Serializer for a pathway's draft_data or published_data field
    """
    title = serializers.CharField(default="Pathway")
    description = serializers.CharField(allow_blank=True, default="")
    items = PathwayItemSerializer(many=True, default=list)
    data = serializers.JSONField(default=dict)  # Other arbitrary data like learning objectives


class PathwaySerializer(serializers.Serializer):
    """
    Serializer for a pathway
    """
    # We rename the primary key field to "id" in the REST API since API clients
    # often implement magic functionality for fields with that name, and "key"
    # is a reserved prop name in React. This 'id' field is a string that
    # begins with 'lx-pathway:'. (The numeric ID of the Pathway object in MySQL
    # is not exposed via this API.)
    id = serializers.CharField(source="key", read_only=True)
    # When creating a pathway via the API, one can optionally specify the UUID to use instead of getting a random one:
    uuid = serializers.UUIDField(format='hex_verbose', required=False, write_only=True)
    owner_user_id = serializers.IntegerField(required=False, allow_null=True)
    owner_group_name = serializers.IntegerField(required=False, allow_null=True, source="owner_group.name")
    draft_data = PathwayDataSerializer()
    published_data = PathwayDataSerializer(read_only=True)

    def __init__(self, instance=None, **kwargs):
        """
        Initialize this pathway serializer.
        """
        # If given a Pathway instance, set it into the context so that child serializers like
        # PathwayItemSerializer can access it.
        if instance:
            kwargs.setdefault("context", {})["pathway"] = instance
        super().__init__(instance, **kwargs)
