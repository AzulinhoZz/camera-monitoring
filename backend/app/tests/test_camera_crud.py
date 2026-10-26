import unittest
from unittest.mock import MagicMock, patch
from app.motion_detector import motion_manager
from app.camera_config import config_store

class TestCameraCrudAndPermissions(unittest.TestCase):

    def setUp(self):
        motion_manager.stop_all()

    def test_worker_restart_on_rtsp_url_change(self):
        """Test that changing RTSP URL stops old worker and starts new worker."""
        cam_id = "test_cam_edit_001"
        old_url = "rtsp://10.0.2.2:8554/cam_old"
        new_url = "rtsp://10.0.2.2:8554/cam_new"

        # Start initial worker
        motion_manager.start_detector(cam_id, old_url)
        self.assertTrue(motion_manager.get_status(cam_id)["is_active"])
        self.assertEqual(motion_manager.workers[cam_id].rtsp_url, old_url)

        # Simulate camera RTSP URL edit: stop old worker and start new
        motion_manager.stop_detector(cam_id)
        motion_manager.start_detector(cam_id, new_url)

        self.assertTrue(motion_manager.get_status(cam_id)["is_active"])
        self.assertEqual(motion_manager.workers[cam_id].rtsp_url, new_url)

    def test_delete_camera_stops_worker_and_clears_config(self):
        """Test that deleting a camera stops its OpenCV worker and purges config."""
        cam_id = "test_cam_del_001"
        url = "rtsp://10.0.2.2:8554/cam_del"

        motion_manager.start_detector(cam_id, url)
        self.assertTrue(motion_manager.get_status(cam_id)["is_active"])

        # Perform deletion cleanup
        motion_manager.stop_detector(cam_id)
        config_store.delete_config(cam_id)

        self.assertFalse(motion_manager.get_status(cam_id)["is_active"])
        self.assertNotIn(cam_id, motion_manager.workers)


if __name__ == "__main__":
    unittest.main()
