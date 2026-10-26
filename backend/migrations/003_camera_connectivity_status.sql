-- Migration: Add last_seen_at column to cameras table
-- Description: Tracks the timestamp of the last successful RTSP/HLS connectivity check

ALTER TABLE public.cameras
ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN public.cameras.last_seen_at IS 'Timestamp of the last successful connection check to the camera RTSP stream';
