import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import get_current_user

class TestTenantSecurityAndRoles(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.cameras.create_client")
    def test_driver_a_cannot_access_camera_b(self, mock_create_client):
        # Driver A session
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "driver_A",
            "email": "driverA@test.com",
            "role": "conductor",
            "organization_id": None
        }

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock camera belonging to Driver B
        mock_cams_table = MagicMock()
        mock_cams_table.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "cam_B", "user_id": "driver_B", "organization_id": None}
        ]
        mock_client.table.return_value = mock_cams_table

        # Driver A attempts GET /cameras/cam_B -> 404 or 403 Forbidden
        res = self.client.get("/cameras/cam_B", headers={"Authorization": "Bearer token_A"})
        self.assertIn(res.status_code, [403, 404])

    @patch("app.events.create_client")
    def test_driver_b_cannot_access_events_a(self, mock_create_client):
        # Driver B session
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "driver_B",
            "email": "driverB@test.com",
            "role": "conductor",
            "organization_id": None
        }

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock event belonging to Driver A's camera
        mock_events_table = MagicMock()
        mock_events_table.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "ev_A", "camera_id": "cam_A", "evidence_path": "driver_A/cam_A/ev_A.jpg"}
        ]
        mock_cams_table = MagicMock()
        mock_cams_table.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        def table_side_effect(name):
            if name == "camera_events":
                return mock_events_table
            elif name == "cameras":
                return mock_cams_table
            return MagicMock()

        mock_client.table.side_effect = table_side_effect

        # Driver B attempts GET /events/ev_A/evidence -> 403 Forbidden
        res = self.client.get("/events/ev_A/evidence", headers={"Authorization": "Bearer token_B"})
        self.assertEqual(res.status_code, 403)

    @patch("app.auth.create_client")
    def test_public_signup_defaults_to_conductor_role(self, mock_create_client):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_user = MagicMock()
        mock_user.id = "new_user_123"
        mock_user.email = "newdriver@test.com"
        mock_user.user_metadata = {"full_name": "Nuevo Conductor"}

        mock_res = MagicMock()
        mock_res.user = mock_user
        mock_res.session = None

        mock_client.auth.sign_up.return_value = mock_res
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        signup_payload = {
            "full_name": "Nuevo Conductor",
            "email": "newdriver@test.com",
            "password": "Password123!"
        }

        res = self.client.post("/auth/register", json=signup_payload)
        self.assertEqual(res.status_code, 201)
        json_data = res.json()
        self.assertEqual(json_data["user"]["role"], "conductor")

if __name__ == "__main__":
    unittest.main()
