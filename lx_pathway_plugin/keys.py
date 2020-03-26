"""
OpaqueKey subclass for LabXchange Pathways
"""
# pylint: disable=abstract-method
import re
import warnings
from uuid import UUID

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import LearningContextKey, UsageKeyV2
from opaque_keys.edx.locator import CheckFieldMixin


class PathwayLocator(LearningContextKey):
    """
    An :class:`opaque_keys.OpaqueKey` identifying a pathway.

    A pathway is a short sequence of XBlocks.

    When serialized, these keys look like:
        lx-pathway:3f3314f8-5f59-4215-b284-09fb578f561e
    """
    CANONICAL_NAMESPACE = 'lx-pathway'
    KEY_FIELDS = ('uuid', )
    __slots__ = KEY_FIELDS
    CHECKED_INIT = False
    is_course = False

    # pylint: disable=no-member

    def __init__(self, uuid):
        """
        Instantiate a new PathwayLocator
        """
        if not isinstance(uuid, UUID):
            uuid_str = uuid
            uuid = UUID(uuid_str)
            # Raise an error if this UUID is not in standard form, to prevent inconsistent UUID serialization
            if uuid_str != str(uuid):
                raise InvalidKeyError(self.__class__, u"uuid field got UUID string that's not in standard form")

        super().__init__(uuid=uuid)

    def _to_string(self):
        """
        Return a string representing this PathwayLocator
        """
        return str(self.uuid)

    @classmethod
    def _from_string(cls, serialized):
        """
        Return a BundleDefinitionLocator by parsing the given serialized string
        """
        uuid_str = serialized
        try:
            return cls(uuid=uuid_str)
        except (ValueError, TypeError):
            raise InvalidKeyError(cls, serialized)


class PathwayUsageLocator(CheckFieldMixin, UsageKeyV2):
    """
    An XBlock in a LabXchange pathway.

    When serialized, these keys look like:
        lx-pb:3f3314f8-5f59-4215-b284-09fb578f561e:html:ec1d6c9f
    or
        lx-pb:3f3314f8-5f59-4215-b284-09fb578f561e:html:ec1d6c9f:child1
    """
    CANONICAL_NAMESPACE = 'lx-pb'  # "LabXchange Pathway Block"
    KEY_FIELDS = ('pathway_key', 'block_type', 'usage_id', 'child_usage_id')
    __slots__ = KEY_FIELDS

    # Allow usage IDs to contain unicode characters
    USAGE_ID_REGEXP = re.compile(r'^[\w\-.]+$', flags=re.UNICODE)

    # pylint: disable=no-member

    def __init__(self, pathway_key, block_type, usage_id, child_usage_id=None):
        """
        Construct a PathwayUsageLocator
        """
        if not isinstance(pathway_key, PathwayLocator):
            raise TypeError("pathway_key must be a PathwayLocator")
        self._check_key_string_field("block_type", block_type)
        self._check_key_string_field("usage_id", usage_id, regexp=self.USAGE_ID_REGEXP)
        if child_usage_id is not None:
            self._check_key_string_field("child_usage_id", usage_id, regexp=self.USAGE_ID_REGEXP)
        super().__init__(
            pathway_key=pathway_key,
            block_type=block_type,
            usage_id=usage_id,
            child_usage_id=child_usage_id,
        )

    @property
    def context_key(self):
        return self.pathway_key

    @property
    def block_id(self):
        """
        Get the 'block ID' which is another name for the usage ID.
        """
        return self.usage_id

    def _to_string(self):
        """
        Serialize this key as a string
        """
        parts = [str(self.pathway_key.uuid), self.block_type, self.usage_id]
        if self.child_usage_id:
            parts.append(self.child_usage_id)
        return ":".join(parts)

    @classmethod
    def _from_string(cls, serialized):
        """
        Instantiate this key from a serialized string
        """
        parts = serialized.split(':')
        if len(parts) < 3 or len(parts) > 4:
            raise InvalidKeyError(cls, serialized)
        (pathway_uuid, block_type, usage_id) = parts[0:3]
        pathway_key = PathwayLocator(uuid=pathway_uuid)
        try:
            child_usage_id = parts[3]
        except IndexError:
            child_usage_id = None
        return cls(pathway_key, block_type, usage_id, child_usage_id)

    def html_id(self):
        """
        Return an id which can be used on an html page as an id attr of an html
        element. This is only in here for backwards-compatibility with XModules;
        don't use in new code.
        """
        warnings.warn(".html_id is deprecated", DeprecationWarning, stacklevel=2)
        # HTML5 allows ID values to contain any characters at all other than spaces.
        # These key types don't allow spaces either, so no transform is needed.
        return str(self)
