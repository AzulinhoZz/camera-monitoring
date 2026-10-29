-- Additive query indexes only. Run with psql autocommit, not inside BEGIN.
-- CONCURRENTLY avoids a write-blocking table build; inspect invalid indexes
-- after interrupted builds before retrying. Never apply automatically at startup.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_camera_events_camera_timeline_v1
 ON public.camera_events(camera_id,detected_at DESC,id DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_camera_events_pending_window_v1
 ON public.camera_events(camera_id,detected_at DESC) WHERE review_status='pending';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_camera_events_rule_window_v1
 ON public.camera_events(camera_id,(vision_metadata->>'rule_id'),detected_at DESC,id DESC)
 WHERE (vision_metadata->>'rule_id') IS NOT NULL;
DO $$
BEGIN
 IF (SELECT count(*) FROM pg_index WHERE indexrelid IN (
  to_regclass('public.idx_camera_events_camera_timeline_v1'),
  to_regclass('public.idx_camera_events_pending_window_v1'),
  to_regclass('public.idx_camera_events_rule_window_v1')) AND indisvalid AND indisready)<>3 THEN
  RAISE EXCEPTION 'Event query indexes incomplete or invalid; inspect before retry';
 END IF;
END $$;
