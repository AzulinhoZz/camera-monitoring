-- Migration: Add sensitivity and schedule configuration columns to camera_motion_configs
-- Description: Supports low, medium, high, custom sensitivity presets and 24/7 or scheduled detection with IANA timezone evaluation

ALTER TABLE public.camera_motion_configs
ADD COLUMN IF NOT EXISTS sensitivity_preset TEXT DEFAULT 'medium',
ADD COLUMN IF NOT EXISTS schedule_type TEXT DEFAULT '24/7',
ADD COLUMN IF NOT EXISTS schedule_days TEXT[] DEFAULT ARRAY['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
ADD COLUMN IF NOT EXISTS start_time TEXT DEFAULT '00:00:00',
ADD COLUMN IF NOT EXISTS end_time TEXT DEFAULT '23:59:59',
ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'America/Mexico_City';

COMMENT ON COLUMN public.camera_motion_configs.sensitivity_preset IS 'low, medium, high, custom';
COMMENT ON COLUMN public.camera_motion_configs.schedule_type IS '24/7 or scheduled';
COMMENT ON COLUMN public.camera_motion_configs.timezone IS 'IANA timezone ID (e.g. America/Mexico_City)';
