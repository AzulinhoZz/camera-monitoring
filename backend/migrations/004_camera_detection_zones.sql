-- Migration: Create camera_detection_zones table in Supabase
-- Description: Stores configurable polygon detection zones per camera with normalized [0.0, 1.0] coordinates

CREATE TABLE IF NOT EXISTS public.camera_detection_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES public.cameras(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Zona 1',
    polygon_json JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for camera_id lookups
CREATE INDEX IF NOT EXISTS idx_camera_detection_zones_camera_id ON public.camera_detection_zones(camera_id);

-- Trigger for automatic updated_at timestamp
DROP TRIGGER IF EXISTS set_camera_detection_zones_updated_at ON public.camera_detection_zones;
CREATE TRIGGER set_camera_detection_zones_updated_at
BEFORE UPDATE ON public.camera_detection_zones
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE public.camera_detection_zones ENABLE ROW LEVEL SECURITY;

-- RLS Policies checking camera ownership through public.cameras
DROP POLICY IF EXISTS "Users can view own camera detection zones" ON public.camera_detection_zones;
CREATE POLICY "Users can view own camera detection zones"
ON public.camera_detection_zones FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM public.cameras
        WHERE public.cameras.id = public.camera_detection_zones.camera_id
        AND public.cameras.user_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Users can insert own camera detection zones" ON public.camera_detection_zones;
CREATE POLICY "Users can insert own camera detection zones"
ON public.camera_detection_zones FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.cameras
        WHERE public.cameras.id = public.camera_detection_zones.camera_id
        AND public.cameras.user_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Users can update own camera detection zones" ON public.camera_detection_zones;
CREATE POLICY "Users can update own camera detection zones"
ON public.camera_detection_zones FOR UPDATE
USING (
    EXISTS (
        SELECT 1 FROM public.cameras
        WHERE public.cameras.id = public.camera_detection_zones.camera_id
        AND public.cameras.user_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Users can delete own camera detection zones" ON public.camera_detection_zones;
CREATE POLICY "Users can delete own camera detection zones"
ON public.camera_detection_zones FOR DELETE
USING (
    EXISTS (
        SELECT 1 FROM public.cameras
        WHERE public.cameras.id = public.camera_detection_zones.camera_id
        AND public.cameras.user_id = auth.uid()
    )
);
