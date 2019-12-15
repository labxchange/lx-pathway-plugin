"""
Definition of "Pathway" as a learning context.
"""
import logging

from opaque_keys.edx.keys import UsageKey
from opaque_keys.edx.locator import BundleDefinitionLocator
from openedx.core.djangoapps.xblock.learning_context import LearningContext
from openedx.core.djangoapps.xblock.learning_context.manager import get_learning_context_impl

from lx_pathway_plugin.models import Pathway
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
        if not isinstance(usage_key, PathwayUsageLocator):
            raise TypeError("Invalid pathway usage key")
        try:
            pathway = Pathway.objects.get(uuid=usage_key.pathway_key.uuid)
        except Pathway.DoesNotExist:
            log.exception("Pathway does not exist for pathway usage key {}".format(usage_key))
            return None
        if 'force_draft' in kwargs:
            use_draft = kwargs['force_draft']
        else:
            use_draft = self.use_draft
        pathway_data = getattr(pathway, 'draft_data' if use_draft else 'published_data')
        original_usage_id = None
        version = None
        for item in pathway_data["items"]:
            if item["id"] == usage_key.usage_id:
                original_usage_id = UsageKey.from_string(item["original_usage_id"])
                version = item["version"]
                break
        if original_usage_id is None:
            return None
        original_learning_context = get_learning_context_impl(original_usage_id)
        original_def_key = original_learning_context.definition_for_usage(original_usage_id)
        if original_def_key is None:
            return None
        # Now, are we talking about the block itself (that original_usage_id refers to) or one of its descendants?
        if usage_key.child_usage_id:
            # This is a child or other descendant of the block:
            olx_path = "{}/{}/definition.xml".format(usage_key.block_type, usage_key.child_usage_id)
        else:
            olx_path = original_def_key.olx_path
        # Now create the BundleDefinitionLocator, which is the same as original_def_key
        # except possibly with a specific version number
        return BundleDefinitionLocator(
            bundle_uuid=original_def_key.bundle_uuid,
            block_type=usage_key.block_type,
            olx_path=olx_path,
            bundle_version=version if version else original_def_key.bundle_version,
        )

    def usage_for_child_include(self, parent_usage, parent_definition, parsed_include):
        """
        Method that the runtime uses when loading a block's child, to get the
        ID of the child.

        The child is always from an <xblock-include /> element.
        """
        assert isinstance(parent_usage, PathwayUsageLocator)
        # We need some kind of 'child_usage_id' part that can go into this child's
        # usage key that provides enough information for definition_for_usage to
        # use to get the BundleDefinitionLocator for the child (or its child...)
        if parsed_include.link_id:
            raise NotImplementedError("LabXchange pathways don't yet support linked content in other bundles")
            # Links could be supported, and there are a couple ways to do that.
            # A pretty good way is probably to make the 'child_usage_id' encode
            # any and all links that must be followed from the bundle of the
            # original parent block (the block that's added directly to the
            # pathway) to get to this descendant's bundle.
            # e.g. if the pathway has a block in bundle A and it has a child in
            # bundle B via link "a2b", and that child has another child in the
            # same bundle, and that child has a child in bundle C via link "b2c"
            # and that last child has definition_id "html1" then the
            # "child_usage_id" could be "a2b/b2c/html1", and
            # definition_for_usage() could use those link names to traverse the
            # bundle links and then find the definition XML file, without
            # needing to know anything else.
        return PathwayUsageLocator(
            pathway_key=parent_usage.pathway_key,
            block_type=parsed_include.block_type,
            usage_id=parent_usage.usage_id,
            child_usage_id=parsed_include.definition_id,
        )
