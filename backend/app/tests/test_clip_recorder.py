import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from app.clip_recorder import FrameRingBuffer, record_and_upload_clip

class TestClipRecorder(unittest.TestCase):

    def test_frame_ring_buffer(self):
        buf = FrameRingBuffer(maxlen=5)
        for i in range(10):
            frame = np.full((10, 10, 3), i, dtype=np.uint8)
            buf.append(frame)

        frames = buf.get_frames_copy()
        self.assertEqual(len(frames), 5)
        self.assertEqual(frames[-1][0, 0, 0], 9)

    @patch("app.clip_recorder.create_client")
    def test_record_and_upload_clip(self, mock_client):
        pre_frames = [np.full((100, 100, 3), 100, dtype=np.uint8) for _ in range(5)]
        provider = lambda: np.full((100, 100, 3), 150, dtype=np.uint8)

        record_and_upload_clip(
            event_id="ev_clip_test",
            user_id="usr_123",
            camera_id="cam_123",
            pre_event_frames=pre_frames,
            post_event_provider=provider,
            post_duration_sec=0.2,
            fps=10
        )

        mock_client.return_value.storage.from_.assert_called_with("motion-clips")

if __name__ == "__main__":
    unittest.main()
