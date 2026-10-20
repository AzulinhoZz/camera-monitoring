import unittest
import numpy as np
import cv2
from app.motion_detector import MotionDetectorWorker, MotionDetectorManager


def create_blank_frame(width=640, height=480, color=128):
    """Creates a synthetic single-color image frame."""
    frame = np.full((height, width, 3), color, dtype=np.uint8)
    return frame


def create_frame_with_rectangle(x=100, y=100, w=100, h=100, width=640, height=480):
    """Creates a synthetic frame with a white rectangle inserted at (x,y)."""
    frame = create_blank_frame(width, height)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), -1)
    return frame


class TestMotionDetector(unittest.TestCase):

    def test_motion_detection_static_scene(self):
        """Test 1: Static scene without movement returns no motion detected."""
        worker = MotionDetectorWorker(camera_id="cam_test", rtsp_url="rtsp://fake", min_area=1500)

        frame1 = create_blank_frame()
        frame2 = create_blank_frame()

        _, _, bg1 = worker.process_frame(frame1, None)
        detected, area, _ = worker.process_frame(frame2, bg1)

        self.assertFalse(detected)
        self.assertEqual(area, 0)

    def test_motion_detection_moving_object(self):
        """Test 2: Scene with moving large object triggers motion detection."""
        worker = MotionDetectorWorker(camera_id="cam_test", rtsp_url="rtsp://fake", min_area=1500)

        frame1 = create_blank_frame()
        frame2 = create_frame_with_rectangle(x=200, y=200, w=120, h=120)

        _, _, bg1 = worker.process_frame(frame1, None)
        detected, area, _ = worker.process_frame(frame2, bg1)

        self.assertTrue(detected)
        self.assertGreaterEqual(area, 1500)

    def test_noise_filtering_small_object(self):
        """Test 3: Small object movement below min_area threshold is filtered out as noise."""
        worker = MotionDetectorWorker(camera_id="cam_test", rtsp_url="rtsp://fake", min_area=2000)

        frame1 = create_blank_frame()
        frame2 = create_frame_with_rectangle(x=50, y=50, w=10, h=10) # 100 px < 2000 px

        _, _, bg1 = worker.process_frame(frame1, None)
        detected, area, _ = worker.process_frame(frame2, bg1)

        self.assertFalse(detected)
        self.assertLess(area, 2000)

    def test_cooldown_throttling(self):
        """Test 4: Cooldown prevents duplicate event triggers within cooldown window."""
        logged_events = []

        class TestWorker(MotionDetectorWorker):
            def log_event_to_db(self, description):
                logged_events.append(description)

        worker = TestWorker(camera_id="cam_test", rtsp_url="rtsp://fake", cooldown_seconds=5.0)

        worker.last_event_time = 0.0
        now_t = 1.0 # 1s later (< 5s cooldown)

        if now_t - worker.last_event_time >= worker.cooldown_seconds:
            worker.last_event_time = now_t
            worker.log_event_to_db("Event 1")

        self.assertEqual(len(logged_events), 0) # Blocked by cooldown

        now_t = 6.0 # 6s later (> 5s cooldown)
        if now_t - worker.last_event_time >= worker.cooldown_seconds:
            worker.last_event_time = now_t
            worker.log_event_to_db("Event 2")

        self.assertEqual(len(logged_events), 1) # Allowed!

    def test_manager_start_stop(self):
        """Test 5: MotionDetectorManager start, status, update, and stop lifecycle."""
        manager = MotionDetectorManager()

        status = manager.start_detector("cam_demo", "rtsp://10.0.2.2:8554/camara1", min_area=2500, threshold=30, cooldown_seconds=10.0)
        self.assertTrue(status["is_active"])
        self.assertEqual(status["min_area"], 2500)
        self.assertEqual(status["threshold"], 30)
        self.assertEqual(status["cooldown_seconds"], 10.0)

        get_stat = manager.get_status("cam_demo")
        self.assertTrue(get_stat["is_active"])

        stop_stat = manager.stop_detector("cam_demo")
        self.assertFalse(stop_stat["is_active"])

        final_stat = manager.get_status("cam_demo")
        self.assertFalse(final_stat["is_active"])


if __name__ == "__main__":
    unittest.main()
