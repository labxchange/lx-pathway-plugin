"""
Definition of "Pathway" as a learning context.
"""
import logging

from edx_django_utils.cache.utils import RequestCache
from opaque_keys.edx.keys import UsageKey
from openedx.core.djangoapps.xblock.learning_context import LearningContext
from openedx.core.djangoapps.xblock.learning_context.manager import get_learning_context_impl

from lx_pathway_plugin.keys import PathwayUsageLocator

log = logging.getLogger(__name__)


class PathwayContextImpl(LearningContext):
    """
    Implements LabXchange "Pathways" as a learning context.

    Every pathway is identified by a UUID, which is also the UUID of a bundle
    in Blockstore that holds its data.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.use_draft = kwargs.get('use_draft', None)

    def can_edit_block(self, user, usage_key):
        """
        Does the specified usage key exist in its context, and if so, does the
        specified user (which may be an AnonymousUser) have permission to edit
        it?

        Must return a boolean.
        """
        def_key = self.definition_for_usage(usage_key)
        if not def_key:
            return False
        # TODO: implement permissions
        return True

    def can_view_block(self, user, usage_key):
        """
        Does the specified usage key exist in its context, and if so, does the
        specified user (which may be an AnonymousUser) have permission to view
        it and interact with it (call handlers, save user state, etc.)?

        Must return a boolean.
        """
        def_key = self.definition_for_usage(usage_key)
        if not def_key:
            return False
        # TODO: implement permissions
        return True

    def definition_for_usage(self, usage_key, **kwargs):
        """
        Given a usage key for an XBlock in this context, return the
        BundleDefinitionLocator which specifies the actual XBlock definition
        (as a path to an OLX in a specific blockstore bundle).

        Must return a BundleDefinitionLocator if the XBlock exists in this
        context, or None otherwise.
        """
        original_usage_id = self._original_usage_id(usage_key, **kwargs)
        if not original_usage_id:
            return None
        original_learning_context = get_learning_context_impl(original_usage_id)
        return original_learning_context.definition_for_usage(original_usage_id)

    def usage_for_child_include(self, parent_usage, parent_definition, parsed_include):
        """
        Method that the runtime uses when loading a block's child, to get the
        ID of the child.

        The child is always from an <xblock-include /> element.
        """
        assert isinstance(parent_usage, PathwayUsageLocator)
        # We need some kind of 'child_usage_id' part that can go into this child's
        orig_parent = self._original_usage_id(parent_usage)
        orig_learning_context = get_learning_context_impl(orig_parent)
        orig_usage_id = orig_learning_context.usage_for_child_include(orig_parent, parent_definition, parsed_include)
        return PathwayUsageLocator(
            pathway_key=parent_usage.pathway_key,
            block_type=parsed_include.block_type,
            usage_id=parent_usage.usage_id,  # This part of our pathway key is the same for all descendant blocks.
            child_usage_id=orig_usage_id.usage_id,
        )

    def _original_usage_id(self, pathway_usage_key):
        """
        Given a usage key for an XBlock in this context, return the original usage
        key.
        """
        pathway_data = self._pathway_data(pathway_usage_key.pathway_key)
        original_usage_id = None
        for item in pathway_data["items"]:
            if item["id"] == pathway_usage_key.usage_id:
                original_usage_id = UsageKey.from_string(item["original_usage_id"])
                break
        if pathway_usage_key.child_usage_id:
            original_usage_id = replace_opaque_key(
                original_usage_id,
                block_type=pathway_usage_key.block_type,
                usage_id=pathway_usage_key.child_usage_id,
            )
        return original_usage_id


def replace_opaque_key(existing_key, **kwargs):
    """
    Copy of OpaqueKey.replace() that doesn't set the 'deprecated' field.

    Avoids:
        TypeError: __init__() got an unexpected keyword argument 'deprecated'
    """
    existing_values = {key: getattr(existing_key, key) for key in existing_key.KEY_FIELDS}
    if all(value == existing_values[key] for (key, value) in kwargs.items()):
        return existing_key
    existing_values.update(kwargs)
    return type(existing_key)(**existing_values)
