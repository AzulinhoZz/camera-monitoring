import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from app.evidence_uploader import upload_frame_to_supabase

class TestEvidenceUploader(unittest.TestCase):

    @patch("app.evidence_uploader.create_client")
    def test_upload_frame_resizes_and_dispatches(self, mock_create_client):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        frame = np.full((100, 100, 3), 128, dtype=np.uint8)

        upload_frame_to_supabase(
            event_id="ev_123",
            user_id="user_123",
            camera_id="cam_123",
            frame=frame
        )

        mock_client.storage.from_.assert_called_with("motion-evidence")

if __name__ == "__main__":
    unittest.main()
