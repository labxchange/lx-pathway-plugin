"""
Test for the LabXchange pathway learning context REST API.

These tests need to be run within the LMS's virtualenv.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from copy import deepcopy

from django.test import override_settings
from opaque_keys.edx.keys import UsageKey
from organizations.models import Organization
from rest_framework.test import APIClient, APITestCase

from openedx.core.djangoapps.content_libraries import api as library_api
from openedx.core.djangoapps.xblock import api as xblock_api
from openedx.core.lib import blockstore_api
from student.tests.factories import UserFactory

URL_CREATE_PATHWAY = '/api/lx-pathways/v1/pathway/'
URL_GET_PATHWAY = URL_CREATE_PATHWAY + '{pathway_id}/'


@override_settings(LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES=['lx-test-user'])
class PathwayApiTests(APITestCase):
    """
    Test for the LabXchange pathway learning context REST API
    """
    @classmethod
    def setUpClass(cls):
        """
        Create some XBlocks in a content library for use in any tests
        """
        super(PathwayApiTests, cls).setUpClass()
        # Create a couple libraries and blocks that can be used for these tests:
        cls.collection = blockstore_api.create_collection("Pathway Test Collection")
        cls.organization = Organization.objects.create(name="TestOrg", short_name="TestOrg")
        cls.lib1 = library_api.create_library(
            collection_uuid=cls.collection.uuid,
            org=cls.organization,
            slug="lx-pathway-lib1",
            title="Pathway Test Lib",
            description="",
        )
        cls.problem_block1_id = library_api.create_library_block(cls.lib1.key, "problem", "p1").usage_key
        library_api.publish_changes(cls.lib1.key)
        cls.lib2 = library_api.create_library(
            collection_uuid=cls.collection.uuid,
            org=cls.organization,
            slug="lx-pathway-lib2",
            title="Pathway Test Lib 2",
            description="",
        )
        cls.html_block2_id = library_api.create_library_block(cls.lib2.key, "html", "h2").usage_key
        library_api.publish_changes(cls.lib2.key)

    def setUp(self):
        """
        Set up used by each test
        """
        super(PathwayApiTests, self).setUp()
        # Create a service user that's authorized to use the API:
        self.user = UserFactory(username='lx-test-user', password='edx')
        self.client = APIClient()
        self.client.login(username=self.user.username, password='edx')
        # Create another user that's not authorized to use this API
        self.other_user = UserFactory(username='other-test-user', password='edx')
        self.other_client = APIClient()
        self.other_client.login(username=self.other_user.username, password='edx')

    @property
    def pathway_initial_data(self):
        """
        Get some initial data that can be used to test pathway creation
        """
        return {
            "owner_user_id": self.user.id,
            "draft_data": {
                "title": "A Test Pathway",
                "description": "A pathway for testing",
                "data": {
                    "arbitrary": "data",
                },
                "items": [
                    {
                        "original_usage_id": str(self.problem_block1_id),
                        "version": 0,
                        "data": {"notes": "this is a test note."},
                    },
                    {
                        "original_usage_id": str(self.html_block2_id),
                        "version": 0,
                    },
                ],
            },
        }

    def test_pathway_create_other_user(self):
        """
        Verify that users without explicit authorization cannot create pathways.
        """
        response = self.other_client.post(URL_CREATE_PATHWAY, self.pathway_initial_data, format='json')
        self.assertEqual(response.status_code, 403)

    def test_pathway_lifecycle(self):  # pylint: disable=too-many-statements
        """
        Test Pathway CRUD
        """
        # Create a new pathway:
        response = self.client.post(URL_CREATE_PATHWAY, self.pathway_initial_data, format='json')
        self.assertEqual(response.status_code, 200)
        pathway_id = response.data["id"]

        # Get the resulting pathway:
        pathway_url = URL_GET_PATHWAY.format(pathway_id=pathway_id)
        # Other users cannot get the new pathway:
        other_response = self.other_client.get(pathway_url)
        self.assertEqual(other_response.status_code, 403)
        # But our authorized user can:
        response = self.client.get(pathway_url)
        self.assertEqual(response.status_code, 200)
        orig_data = response.data
        self.assertEqual(orig_data["id"], pathway_id)
        self.assertEqual(orig_data["owner_user_id"], self.user.id)
        self.assertEqual(orig_data["owner_group_name"], None)
        self.assertEqual(orig_data["draft_data"]["items"][0]["original_usage_id"], str(self.problem_block1_id))
        # We specified version=0 when creating the pathway, which means "find the current version" and freeze the item
        # at that version, so we expect the version to be 1, since the library has been saved 1 time.
        self.assertEqual(orig_data["draft_data"]["items"][0]["version"], 1)
        self.assertEqual(orig_data["draft_data"]["items"][0]["data"]["notes"], "this is a test note.")
        self.assertEqual(orig_data["draft_data"]["items"][1]["original_usage_id"], str(self.html_block2_id))
        self.assertEqual(len(orig_data["draft_data"]["items"]), 2)
        self.assertEqual(orig_data["published_data"]["items"], [])
        item1_pathway_id = orig_data["draft_data"]["items"][0]["usage_id"]
        item2_pathway_id = orig_data["draft_data"]["items"][1]["usage_id"]

        # Now publish the pathway:
        response = self.client.post(pathway_url + 'publish/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get(pathway_url)
        self.assertEqual(response.status_code, 200)
        # The new published data/items should equal the previous draft data:
        self.assertEqual(response.data["published_data"], orig_data["draft_data"])

        # Now we'll add a second copy of the HTML block to the pathway:
        new_draft_data = deepcopy(orig_data["draft_data"])
        new_draft_data["items"].append({"original_usage_id": str(self.html_block2_id), "version": 0})
        # Other users cannot change the pathway:
        other_response = self.other_client.patch(pathway_url, {"draft_data": new_draft_data}, format="json")
        self.assertEqual(other_response.status_code, 403)
        # But our authorized user can:
        response = self.client.patch(pathway_url, {"draft_data": new_draft_data}, format="json")
        self.assertEqual(response.status_code, 200)
        # The IDs of the existing items in the pathway must not have changed:
        self.assertEqual(response.data["draft_data"]["items"][0]["usage_id"], item1_pathway_id)
        self.assertEqual(response.data["draft_data"]["items"][1]["usage_id"], item2_pathway_id)
        # And now a new item was added:
        self.assertEqual(len(response.data["draft_data"]["items"]), 3)

        # Now revert the changes, going back to two items:
        response = self.client.delete(pathway_url + 'publish/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get(pathway_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["draft_data"]["items"]), 2)
        self.assertEqual(len(response.data["published_data"]["items"]), 2)
        self.assertEqual(response.data["draft_data"], orig_data["draft_data"])
        self.assertEqual(response.data["published_data"], orig_data["draft_data"])

        # Now view one of the XBlocks in the pathway.
        # This checks that all of the normal XBlock runtime APIs are working with blocks in a pathway context:
        item1_pathway_key = UsageKey.from_string(item1_pathway_id)
        block = xblock_api.load_block(item1_pathway_key, user=self.other_user)
        self.assertEqual(block.attempts, 0)  # Test loading a field value

        # Now delete the pathway:
        # Other users cannot delete the pathway:
        other_response = self.other_client.delete(pathway_url)
        self.assertEqual(other_response.status_code, 403)
        # But our authorized user can:
        response = self.client.delete(pathway_url)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(pathway_url)
        self.assertEqual(response.status_code, 404)  # Pathway is deleted.

    def test_pathway_create_with_uuid(self):
        """
        Test that a pathway can be created with a specified UUID (for migration
        purposes, to migrate existing pathways from the old to new system
        without changing their UUID)
        """
        chosen_uuid = "b0fd731a-5bab-4fe2-8491-405292e5176e"
        initial_data = self.pathway_initial_data.copy()
        initial_data["uuid"] = chosen_uuid
        response = self.client.post(URL_CREATE_PATHWAY, initial_data, format='json')
        self.assertEqual(response.status_code, 200)
        pathway_id = response.data["id"]
        self.assertIn(chosen_uuid, pathway_id)
