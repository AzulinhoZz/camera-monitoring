import unittest
from unittest.mock import patch, MagicMock
from app.retention_manager import retention_manager, VALID_RETENTION_DAYS

class TestRetentionManager(unittest.TestCase):

    def test_valid_retention_days(self):
        self.assertIn(7, VALID_RETENTION_DAYS)
        self.assertIn(15, VALID_RETENTION_DAYS)
        self.assertIn(30, VALID_RETENTION_DAYS)
        self.assertIn(90, VALID_RETENTION_DAYS)

    @patch.object(retention_manager, "get_user_config")
    @patch("app.retention_manager.get_supabase_client")
    def test_dry_run_does_not_execute_deletion(self, mock_get_client, mock_get_cfg):
        mock_get_cfg.return_value = {"user_id": "usr_test", "retention_days": 30, "auto_cleanup_enabled": False}
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock cameras query
        mock_cams = MagicMock()
        mock_cams.select.return_value.eq.return_value.execute.return_value.data = [{"id": "cam_1"}]

        # Mock events query
        mock_events = MagicMock()
        mock_events.select.return_value.in_.return_value.lt.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "ev_1", "camera_id": "cam_1", "evidence_path": "usr_test/cam_1/ev_1.jpg", "clip_path": "usr_test/cam_1/ev_1.mp4", "is_protected": False}
        ]
        mock_events.select.return_value.eq.return_value.execute.return_value.data = [{"is_protected": False}]

        def table_router(table_name):
            if table_name == "cameras":
                return mock_cams
            elif table_name == "camera_events":
                return mock_events
            return MagicMock()

        mock_client.table.side_effect = table_router

        res = retention_manager.cleanup_expired_evidence(user_id="usr_test", dry_run=True, is_auto_trigger=False)

        self.assertTrue(res["dry_run"])
        self.assertEqual(res["deleted_photos"], 1)
        self.assertEqual(res["deleted_clips"], 1)

        # Ensure remove was NEVER called in dry-run mode!
        mock_client.storage.from_.return_value.remove.assert_not_called()

    @patch.object(retention_manager, "get_user_config")
    @patch("app.retention_manager.get_supabase_client")
    def test_auto_cleanup_disabled_aborts_automatic_trigger(self, mock_get_client, mock_get_cfg):
        mock_get_cfg.return_value = {"user_id": "usr_test", "retention_days": 30, "auto_cleanup_enabled": False}
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        res = retention_manager.cleanup_expired_evidence(user_id="usr_test", dry_run=False, is_auto_trigger=True)

        self.assertEqual(res["status"], "aborted_disabled")
        self.assertEqual(res["deleted_photos"], 0)
        self.assertEqual(res["deleted_clips"], 0)

    @patch.object(retention_manager, "get_user_config")
    @patch("app.retention_manager.get_supabase_client")
    def test_protected_events_never_deleted(self, mock_get_client, mock_get_cfg):
        mock_get_cfg.return_value = {"user_id": "usr_test", "retention_days": 30, "auto_cleanup_enabled": True}
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_cams = MagicMock()
        mock_cams.select.return_value.eq.return_value.execute.return_value.data = [{"id": "cam_1"}]

        mock_events = MagicMock()
        mock_events.select.return_value.in_.return_value.lt.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

        def table_router(table_name):
            if table_name == "cameras":
                return mock_cams
            elif table_name == "camera_events":
                return mock_events
            return MagicMock()

        mock_client.table.side_effect = table_router

        res = retention_manager.cleanup_expired_evidence(user_id="usr_test", dry_run=False)

        self.assertEqual(res["deleted_photos"], 0)
        self.assertEqual(res["deleted_clips"], 0)

    @patch.object(retention_manager, "get_user_config")
    @patch("app.retention_manager.get_supabase_client")
    def test_storage_removal_failure_does_not_clear_db_path(self, mock_get_client, mock_get_cfg):
        mock_get_cfg.return_value = {"user_id": "usr_test", "retention_days": 30, "auto_cleanup_enabled": True}
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_cams = MagicMock()
        mock_cams.select.return_value.eq.return_value.execute.return_value.data = [{"id": "cam_1"}]

        mock_events = MagicMock()
        mock_events.select.return_value.in_.return_value.lt.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "ev_1", "camera_id": "cam_1", "evidence_path": "usr_test/cam_1/ev_1.jpg", "clip_path": None, "is_protected": False}
        ]
        mock_events.select.return_value.eq.return_value.execute.return_value.data = [{"is_protected": False}]

        def table_router(table_name):
            if table_name == "cameras":
                return mock_cams
            elif table_name == "camera_events":
                return mock_events
            return MagicMock()

        mock_client.table.side_effect = table_router

        # Mock storage remove returning error
        mock_client.storage.from_.return_value.remove.return_value = [{"error": "Storage connection failed"}]

        retention_manager.cleanup_expired_evidence(user_id="usr_test", dry_run=False)

        # DB update for evidence_path MUST NOT be called if storage remove failed!
        mock_events.update.assert_not_called()

    def test_invalid_retention_days_raises_error(self):
        with self.assertRaises(ValueError):
            retention_manager.set_user_config("usr_test", retention_days=45, auto_cleanup_enabled=False)

if __name__ == "__main__":
    unittest.main()
