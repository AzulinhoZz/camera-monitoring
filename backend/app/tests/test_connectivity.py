import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from app.connectivity_checker import check_rtsp_connection

class TestConnectivityChecker(unittest.TestCase):

    @patch("cv2.VideoCapture")
    def test_check_rtsp_connection_success(self, mock_cap):
        mock_instance = MagicMock()
        mock_instance.isOpened.return_value = True
        mock_instance.read.return_value = (True, np.full((100, 100, 3), 128, dtype=np.uint8))
        mock_cap.return_value = mock_instance

        res = check_rtsp_connection("rtsp://10.0.2.2:8554/camara1")
        self.assertTrue(res)

    @patch("cv2.VideoCapture")
    def test_check_rtsp_connection_failure(self, mock_cap):
        mock_instance = MagicMock()
        mock_instance.isOpened.return_value = False
        mock_cap.return_value = mock_instance

        res = check_rtsp_connection("rtsp://invalid_ip:8554/camara1")
        self.assertFalse(res)

if __name__ == "__main__":
    unittest.main()
