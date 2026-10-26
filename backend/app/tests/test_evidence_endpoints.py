import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import get_current_user

class TestEvidenceEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_123", "email": "user@test.com", "role": "conductor", "organization_id": None}

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.events.has_camera_access")
    @patch("app.events.create_client")
    def test_get_event_evidence_available(self, mock_create_client, mock_has_access):
        mock_has_access.return_value = True
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_t = MagicMock()
        mock_t.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "ev_1", "camera_id": "cam_1", "evidence_path": "user_123/cam_1/ev_1.jpg"}
        ]
        mock_client.table.return_value = mock_t
        mock_client.storage.from_.return_value.create_signed_url.return_value = "https://supabase.co/signed-url.jpg"

        res = self.client.get("/events/ev_1/evidence", headers={"Authorization": "Bearer mock_token"})
        self.assertEqual(res.status_code, 200)
        json_data = res.json()
        self.assertTrue(json_data["has_evidence"])
        self.assertEqual(json_data["signed_url"], "https://supabase.co/signed-url.jpg")

    @patch("app.events.create_client")
    def test_get_event_evidence_not_found(self, mock_create_client):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        res = self.client.get("/events/non_existent_ev/evidence", headers={"Authorization": "Bearer mock_token"})
        self.assertEqual(res.status_code, 404)

if __name__ == "__main__":
    unittest.main()
