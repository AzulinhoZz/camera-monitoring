-- Migration: Add evidence_path column to camera_events table
-- Description: Stores path to captured frame image in Supabase Storage private bucket 'motion-evidence'

ALTER TABLE public.camera_events
ADD COLUMN IF NOT EXISTS evidence_path TEXT;

COMMENT ON COLUMN public.camera_events.evidence_path IS 'Path in private Supabase Storage bucket motion-evidence (e.g. user_id/camera_id/event_id.jpg)';
