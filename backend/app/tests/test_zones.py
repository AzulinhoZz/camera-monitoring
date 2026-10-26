import unittest
import numpy as np
import cv2
from app.zone_store import validate_polygon, zone_store
from app.motion_detector import MotionDetectorWorker


def create_blank_frame(width=640, height=480, color=128):
    return np.full((height, width, 3), color, dtype=np.uint8)


def create_frame_with_rect(x=100, y=100, w=100, h=100, width=640, height=480):
    frame = create_blank_frame(width, height)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), -1)
    return frame


class TestDetectionZones(unittest.TestCase):

    def test_polygon_validation(self):
        """Test 1: Polygon geometry validation."""
        valid_poly = [{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.1}, {"x": 0.5, "y": 0.5}]
        self.assertTrue(validate_polygon(valid_poly))

        # Invalid: less than 3 points
        self.assertFalse(validate_polygon([{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.1}]))

        # Invalid: coordinates out of range [0.0, 1.0]
        self.assertFalse(validate_polygon([{"x": -0.1, "y": 0.1}, {"x": 0.5, "y": 0.1}, {"x": 0.5, "y": 0.5}]))
        self.assertFalse(validate_polygon([{"x": 1.5, "y": 0.1}, {"x": 0.5, "y": 0.1}, {"x": 0.5, "y": 0.5}]))

    def test_motion_masked_inside_zone(self):
        """Test 2: Motion occurring INSIDE polygon zone is detected."""
        # Zone covering top-left quadrant (0.0 to 0.5 x and y)
        zone = {
            "id": "z1",
            "polygon": [
                {"x": 0.0, "y": 0.0},
                {"x": 0.5, "y": 0.0},
                {"x": 0.5, "y": 0.5},
                {"x": 0.0, "y": 0.5}
            ]
        }
        worker = MotionDetectorWorker(camera_id="cam_zone_test", rtsp_url="rtsp://fake", min_area=1000, zones=[zone])

        frame1 = create_blank_frame()
        # Motion at x=100, y=100 (inside top-left polygon)
        frame2 = create_frame_with_rect(x=100, y=100, w=100, h=100)

        _, _, bg1 = worker.process_frame(frame1, None)
        detected, area, _ = worker.process_frame(frame2, bg1)

        self.assertTrue(detected)
        self.assertGreaterEqual(area, 1000)

    def test_motion_masked_outside_zone(self):
        """Test 3: Motion occurring OUTSIDE polygon zone is masked out and ignored."""
        # Zone covering top-left quadrant ONLY
        zone = {
            "id": "z1",
            "polygon": [
                {"x": 0.0, "y": 0.0},
                {"x": 0.5, "y": 0.0},
                {"x": 0.5, "y": 0.5},
                {"x": 0.0, "y": 0.5}
            ]
        }
        worker = MotionDetectorWorker(camera_id="cam_zone_test", rtsp_url="rtsp://fake", min_area=1000, zones=[zone])

        frame1 = create_blank_frame()
        # Motion at x=450, y=300 (bottom-right quadrant, OUTSIDE polygon)
        frame2 = create_frame_with_rect(x=450, y=300, w=120, h=120)

        _, _, bg1 = worker.process_frame(frame1, None)
        detected, area, _ = worker.process_frame(frame2, bg1)

        # Motion outside zone must be completely ignored
        self.assertFalse(detected)
        self.assertEqual(area, 0)


if __name__ == "__main__":
    unittest.main()
