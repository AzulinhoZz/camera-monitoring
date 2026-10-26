-- Migration: Add clip_path column to camera_events table
-- Description: Stores path to captured MP4 video clip in Supabase Storage private bucket 'motion-clips'

ALTER TABLE public.camera_events
ADD COLUMN IF NOT EXISTS clip_path TEXT;

COMMENT ON COLUMN public.camera_events.clip_path IS 'Path in private Supabase Storage bucket motion-clips (e.g. user_id/camera_id/event_id.mp4)';
