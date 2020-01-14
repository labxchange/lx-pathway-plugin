"""
Django models for the pathways plugin.
"""
# pylint: disable=abstract-method
from __future__ import absolute_import, division, print_function, unicode_literals

import random
import uuid
from logging import getLogger

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models
from jsonfield.fields import JSONField
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey
from rest_framework import serializers
from xblock.exceptions import XBlockNotFoundError

from openedx.core.djangoapps.xblock.learning_context.manager import get_learning_context_impl

from .keys import PathwayLocator, PathwayUsageLocator

log = getLogger(__name__)
User = get_user_model()


class Pathway(models.Model):
    """
    Model for representing a LabXchange pathway
    """
    # edX models are required to have an integer primary key; we don't use it.
    id = models.AutoField(primary_key=True)
    # UUID of the pathway
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Every pathway is owned either by a user or by a group
    owner_user = models.ForeignKey(User, null=True, blank=True)
    owner_group = models.ForeignKey(Group, null=True, blank=True)
    # The actual pathway data (draft and published version)
    # Contains the list of items, original XBlock IDs, notes, etc.
    # The format of these *_data fields is defined and enforced by PathwayDataSerializer (see below)
    draft_data = JSONField(null=False, blank=True, default=dict)
    published_data = JSONField(null=False, blank=True, default=dict)

    def __str__(self):
        return "<Pathway: {uuid} >".format(uuid=self.uuid)  # xss-lint: disable=python-wrap-html

    @property
    def title(self):
        """
        Get the title of this pathway.
        """
        title = self.published_data.get("title", "")
        if not title:
            title = self.draft_data.get("title", "")
        if not title:
            title = "Pathway {}".format(self.uuid)
        return title

    @property
    def key(self):
        """
        Get the opaque key (LearningContextKey) for this pathway
        """
        return PathwayLocator(uuid=self.uuid)

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Validate and clean before saving.
        """
        # if both owner_user and owner_group are nonexistent or both are existing, error:
        if (not self.owner_user) == (not self.owner_group):
            # We can remove this check and replace it with a proper database constraint
            # once Open edX is upgraded to Django 2.2+
            raise serializers.ValidationError("One and only one of 'user' and 'group' must be set.")
        for data_set in ('draft_data', 'published_data'):
            serializer = PathwayDataSerializer(data=getattr(self, data_set))
            serializer.is_valid(raise_exception=True)
            items = serializer.validated_data["items"]
            num_items = len(items)
            if num_items > 100:
                raise serializers.ValidationError("Too many items in the pathway.")
            id_set = set(item["id"] for item in items)
            if len(id_set) != num_items:
                raise serializers.ValidationError("Some item IDs are not unique.")
            for item in items:
                try:
                    item_usage_key = UsageKey.from_string(item["original_usage_id"])
                except InvalidKeyError:
                    raise serializers.ValidationError("Invalid item ID: {}".format(item["original_usage_id"]))
                if item.get("version") == 0:
                    # Set the "version" to the current newest version
                    item["version"] = lookup_current_version_for_usage_key(item_usage_key)
                if "usage_id" in item:
                    del item["usage_id"]  # This field is only added in the REST API response, never saved to DB
            # Replace the current value of draft_data or published_data with the cleaned version
            setattr(self, data_set, serializer.validated_data)
        return super(Pathway, self).save(*args, **kwargs)

# Serializers


def make_random_id():
    """
    Generate a short, random string that's likely to be unique within the
    pathway. Pathways are capped at 100 items, so we don't have to work too hard
    to ensure this is unique.
    """
    return ''.join(random.SystemRandom().choice('0123456789abcdef') for n in range(8))


def lookup_current_version_for_usage_key(usage_key):
    """
    Determine the current version of the blockstore bundle containing the
    specified XBlock.
    """
    learning_context = get_learning_context_impl(usage_key)
    def_key = learning_context.definition_for_usage(usage_key, force_draft=False)
    if not def_key:
        raise XBlockNotFoundError(usage_key)
    if not def_key.bundle_version:
        raise ValueError("The specified XBlock is from a bundle that has not been published.")
    return def_key.bundle_version


class PathwayItemSerializer(serializers.Serializer):
    """
    Serializer for the data about each item in a pathway
    """
    # The XBlock's usage key in this pathway:
    usage_id = serializers.SerializerMethodField(required=False, read_only=True)
    original_usage_id = serializers.CharField()  # The XBlock's original usage key (in a library, course, or pathway)
    id = serializers.SlugField(default=make_random_id)
    # What version of the XBlock to use (it's actually the xblock's library/course *bundle* version number)
    # If None that means "always use the newest version."
    # If 0, that means "determine what the newest version currently is and use that specific version going forward."
    version = serializers.IntegerField(min_value=0, allow_null=True, default=0)
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
        super(PathwaySerializer, self).__init__(instance, **kwargs)
