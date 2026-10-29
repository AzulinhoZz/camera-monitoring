-- Drop only indexes introduced by 012. Rows/policies/grants are unchanged.
-- Autocommit required; no table or evidence deletion.
DROP INDEX CONCURRENTLY IF EXISTS public.idx_camera_events_rule_window_v1;
DROP INDEX CONCURRENTLY IF EXISTS public.idx_camera_events_pending_window_v1;
DROP INDEX CONCURRENTLY IF EXISTS public.idx_camera_events_camera_timeline_v1;
