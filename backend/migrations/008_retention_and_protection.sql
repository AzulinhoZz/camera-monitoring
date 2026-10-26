-- Migration: Add event protection and user retention policies table
-- Description: Supports protecting important events against auto-deletion and configuring retention days (7, 15, 30, 90)

-- 1. Add is_protected column to camera_events
ALTER TABLE public.camera_events
ADD COLUMN IF NOT EXISTS is_protected BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN public.camera_events.is_protected IS 'Flags event to prevent evidence auto-cleanup';

-- 2. Create user_retention_configs table
CREATE TABLE IF NOT EXISTS public.user_retention_configs (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    retention_days INT NOT NULL DEFAULT 30,
    auto_cleanup_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS on user_retention_configs
ALTER TABLE public.user_retention_configs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own retention config" ON public.user_retention_configs;
CREATE POLICY "Users can view own retention config"
ON public.user_retention_configs FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own retention config" ON public.user_retention_configs;
CREATE POLICY "Users can insert own retention config"
ON public.user_retention_configs FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own retention config" ON public.user_retention_configs;
CREATE POLICY "Users can update own retention config"
ON public.user_retention_configs FOR UPDATE
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own retention config" ON public.user_retention_configs;
CREATE POLICY "Users can delete own retention config"
ON public.user_retention_configs FOR DELETE
USING (auth.uid() = user_id);
