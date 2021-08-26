"""
Test for the LabXchange pathway learning context REST API.

These tests need to be run within Studio's virtualenv:
    make -f /edx/src/lx-pathway-plugin/Makefile validate
"""
from copy import deepcopy
from unittest.mock import patch

from django.test import override_settings
from opaque_keys.edx.keys import UsageKey
from organizations.models import Organization
from rest_framework.test import APIClient, APITestCase

from openedx.core.djangoapps.content_libraries import api as library_api
from openedx.core.djangoapps.xblock import api as xblock_api
from openedx.core.lib import blockstore_api
from common.djangoapps.student.tests.factories import UserFactory

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
        super().setUpClass()
        # Create a couple libraries and blocks that can be used for these tests:
        cls.collection = blockstore_api.create_collection("Pathway Test Collection")
        cls.organization = Organization.objects.create(name="TestOrg", short_name="TestOrg")
        cls.lib1 = library_api.create_library(
            collection_uuid=cls.collection.uuid,
            org=cls.organization,
            slug="lx-pathway-lib1",
            title="Pathway Test Lib",
            description="",
            allow_public_learning=True,
            allow_public_read=True,
            library_type='complex',
            library_license='',
        )
        cls.problem_block1_id = library_api.create_library_block(cls.lib1.key, "problem", "p1").usage_key
        library_api.publish_changes(cls.lib1.key)
        cls.lib2 = library_api.create_library(
            collection_uuid=cls.collection.uuid,
            org=cls.organization,
            slug="lx-pathway-lib2",
            title="Pathway Test Lib 2",
            description="",
            allow_public_learning=True,
            allow_public_read=True,
            library_type='complex',
            library_license='',
        )
        cls.html_block2_id = library_api.create_library_block(cls.lib2.key, "html", "h2").usage_key
        library_api.publish_changes(cls.lib2.key)
        # Create some users:
        cls.user = UserFactory(username='lx-test-user', password='edx')
        cls.other_user = UserFactory(username='other-test-user', password='edx')

    def setUp(self):
        """
        Set up used by each test
        """
        super().setUp()
        # Create a service user that's authorized to use the API:
        self.client = APIClient()
        self.client.login(username=self.user.username, password='edx')
        # Create another user that's not authorized to use this API
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
                        "data": {"notes": "this is a test note."},
                    },
                    {
                        "original_usage_id": str(self.html_block2_id),
                        "version": None,  # Deprecated field kept in to check backwards compatibility
                    },
                ],
            },
        }

    def test_pathway_invalid_original_key(self):
        response = self.client.post(URL_CREATE_PATHWAY, self.pathway_initial_data, format='json')
        self.assertEqual(response.status_code, 200)
        pathway_id = response.data["id"]
        response = self.client.patch(
            URL_GET_PATHWAY.format(pathway_id=pathway_id), {
                "draft_data": {
                    "items": [
                        {'original_usage_id': 'lx-pb:00000000-e4fe-47af-8ff6-123456789000:unit:0ff24589'},
                    ],
                },
            }, format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue('Invalid asset key' in str(response.data))

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
        new_draft_data["items"].append({"original_usage_id": str(self.html_block2_id)})
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

    @patch('xmodule.html_module.add_webpack_to_fragment')
    @patch('xmodule.html_module.shim_xmodule_js')
    def test_complex_xblock_tree(self, _mock1, _mock2):
        """
        Test a Pathway with a deep XBlock tree and inter-bundle-links
        """
        # Create the following XBlock tree
        # Library 2
        #   unit "alpha"
        #     -> link to library 1's bundle ("link1")
        #       -> unit "beta" (in Library 1)
        #         -> html "gamma"
        # Then make sure we can add that whole hierarchy into a pathway.

        beta_key = library_api.create_library_block(self.lib1.key, "unit", "beta").usage_key
        gamma_key = library_api.create_library_block_child(beta_key, "html", "gamma").usage_key
        library_api.set_library_block_olx(gamma_key, '<html>This is gamma.</html>')
        library_api.publish_changes(self.lib1.key)
        library_api.create_bundle_link(self.lib2.key, 'link1', self.lib1.key)
        alpha_key = library_api.create_library_block(self.lib2.key, "unit", "alpha").usage_key
        library_api.set_library_block_olx(alpha_key, '''
            <unit display_name="alpha">
                <xblock-include source="link1" definition="unit/beta" usage_hint="beta" />
            </unit>
        ''')
        library_api.publish_changes(self.lib2.key)

        # Create a new pathway:
        response = self.client.post(URL_CREATE_PATHWAY, {
            "owner_user_id": self.user.id,
            "draft_data": {
                "title": "A Commplex Pathway",
                "description": "Complex pathway for testing",
                "data": {},
                "items": [
                    {"original_usage_id": str(alpha_key)},
                ],
            },
        }, format='json')
        self.assertEqual(response.status_code, 200)
        pathway_id = response.data["id"]
        pathway_url = URL_GET_PATHWAY.format(pathway_id=pathway_id)

        # Now publish the pathway:
        response = self.client.post(pathway_url + 'publish/')
        self.assertEqual(response.status_code, 200)
        # Get the resulting pathway:
        response = self.client.get(pathway_url)
        self.assertEqual(response.status_code, 200)

        # Get the usage ID of the root 'alpha' XBlock:
        alpha_key_pathway = UsageKey.from_string(response.data["published_data"]["items"][0]["usage_id"])
        self.assertNotEqual(alpha_key_pathway, alpha_key)

        block = xblock_api.load_block(alpha_key_pathway, user=self.other_user)
        # Render the block and all its children - make sure even the descendants are rendered:
        fragment = block.render('student_view', context={})
        self.assertIn('This is gamma.', fragment.content)
