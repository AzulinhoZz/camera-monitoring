-- Migration: Create camera_motion_configs table in Supabase
-- Description: Stores OpenCV motion detection settings per camera linked to public.cameras

CREATE TABLE IF NOT EXISTS public.camera_motion_configs (
    camera_id UUID PRIMARY KEY REFERENCES public.cameras(id) ON DELETE CASCADE,
    motion_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    min_area INTEGER NOT NULL DEFAULT 1500 CHECK (min_area > 0 AND min_area <= 500000),
    threshold INTEGER NOT NULL DEFAULT 25 CHECK (threshold >= 1 AND threshold <= 255),
    cooldown_seconds NUMERIC(6, 2) NOT NULL DEFAULT 5.00 CHECK (cooldown_seconds >= 0.1 AND cooldown_seconds <= 3600.0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Function and trigger to handle automatic updated_at timestamps
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_camera_motion_configs_updated_at ON public.camera_motion_configs;
CREATE TRIGGER set_camera_motion_configs_updated_at
BEFORE UPDATE ON public.camera_motion_configs
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE public.camera_motion_configs ENABLE ROW LEVEL SECURITY;

-- RLS Policies linked through public.cameras(user_id)
DROP POLICY IF EXISTS "Users can view own camera motion configs" ON public.camera_motion_configs;
CREATE POLICY "Users can view own camera motion configs"
ON public.camera_motion_configs FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM public.cameras
        WHERE public.cameras.id = public.camera_motion_configs.camera_id
        AND public.cameras.user_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Users can insert own camera motion configs" ON public.camera_motion_configs;
CREATE POLICY "Users can insert own camera motion configs"
ON public.camera_motion_configs FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.cameras
        WHERE public.cameras.id = public.camera_motion_configs.camera_id
        AND public.cameras.user_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Users can update own camera motion configs" ON public.camera_motion_configs;
CREATE POLICY "Users can update own camera motion configs"
ON public.camera_motion_configs FOR UPDATE
USING (
    EXISTS (
        SELECT 1 FROM public.cameras
        WHERE public.cameras.id = public.camera_motion_configs.camera_id
        AND public.cameras.user_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Users can delete own camera motion configs" ON public.camera_motion_configs;
CREATE POLICY "Users can delete own camera motion configs"
ON public.camera_motion_configs FOR DELETE
USING (
    EXISTS (
        SELECT 1 FROM public.cameras
        WHERE public.cameras.id = public.camera_motion_configs.camera_id
        AND public.cameras.user_id = auth.uid()
    )
);
