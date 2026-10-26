-- Setup script for isolated PostgreSQL test environment
-- Recreates pre-migration Supabase schema with 3 auth users, 0 profiles, 12 cameras and events

BEGIN;

-- Drop existing test schemas if any
DROP SCHEMA IF EXISTS auth CASCADE;
DROP SCHEMA IF EXISTS public CASCADE;

CREATE SCHEMA public;
CREATE SCHEMA auth;

-- Grant permissions on public schema
GRANT ALL ON SCHEMA public TO test_admin;
GRANT ALL ON SCHEMA public TO PUBLIC;

-- 1. Create Supabase Auth emulation
CREATE TABLE auth.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    raw_user_meta_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Supabase auth.uid() function simulation
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(
    NULLIF(current_setting('request.jwt.claim.sub', true), ''),
    '00000000-0000-0000-0000-000000000000'
  )::uuid;
$$;

-- Supabase auth.role() function simulation
CREATE OR REPLACE FUNCTION auth.role()
RETURNS TEXT
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(
    NULLIF(current_setting('request.jwt.claim.role', true), ''),
    'authenticated'
  );
$$;

-- 2. Create existing public.profiles table (0 records)
CREATE TABLE public.profiles (
    id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NULL,
    created_at TIMESTAMPTZ NULL DEFAULT NOW()
);

-- 3. Create existing public.cameras table
CREATE TABLE public.cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    rtsp_url TEXT NOT NULL,
    status TEXT DEFAULT 'online',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Create existing public.camera_events table
CREATE TABLE public.camera_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES public.cameras(id) ON DELETE CASCADE,
    event_type TEXT DEFAULT 'motion_detected',
    description TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Insert 3 mock users in auth.users
INSERT INTO auth.users (id, email, raw_user_meta_data) VALUES
('f7210242-a53d-495b-a7d7-26f0e0313ca1', 'driver_a@test.com', '{"full_name": "Conductor A"}'),
('e2831002-3b2c-4925-91b3-5efaf8bace02', 'driver_b@test.com', '{"full_name": "Conductor B"}'),
('d3921003-4c3d-4925-91b3-5efaf8bace03', 'admin1@test.com', '{"full_name": "Admin Flota 1"}');

-- 6. Insert 12 mock cameras (6 for Driver A, 6 for Driver B)
INSERT INTO public.cameras (id, user_id, name, rtsp_url) VALUES
('c1000000-0000-0000-0000-000000000001', 'f7210242-a53d-495b-a7d7-26f0e0313ca1', 'Camara A1', 'rtsp://10.0.2.2:8554/camA1'),
('c1000000-0000-0000-0000-000000000002', 'f7210242-a53d-495b-a7d7-26f0e0313ca1', 'Camara A2', 'rtsp://10.0.2.2:8554/camA2'),
('c1000000-0000-0000-0000-000000000003', 'f7210242-a53d-495b-a7d7-26f0e0313ca1', 'Camara A3', 'rtsp://10.0.2.2:8554/camA3'),
('c1000000-0000-0000-0000-000000000004', 'f7210242-a53d-495b-a7d7-26f0e0313ca1', 'Camara A4', 'rtsp://10.0.2.2:8554/camA4'),
('c1000000-0000-0000-0000-000000000005', 'f7210242-a53d-495b-a7d7-26f0e0313ca1', 'Camara A5', 'rtsp://10.0.2.2:8554/camA5'),
('c1000000-0000-0000-0000-000000000006', 'f7210242-a53d-495b-a7d7-26f0e0313ca1', 'Camara A6', 'rtsp://10.0.2.2:8554/camA6'),
('c2000000-0000-0000-0000-000000000001', 'e2831002-3b2c-4925-91b3-5efaf8bace02', 'Camara B1', 'rtsp://10.0.2.2:8554/camB1'),
('c2000000-0000-0000-0000-000000000002', 'e2831002-3b2c-4925-91b3-5efaf8bace02', 'Camara B2', 'rtsp://10.0.2.2:8554/camB2'),
('c2000000-0000-0000-0000-000000000003', 'e2831002-3b2c-4925-91b3-5efaf8bace02', 'Camara B3', 'rtsp://10.0.2.2:8554/camB3'),
('c2000000-0000-0000-0000-000000000004', 'e2831002-3b2c-4925-91b3-5efaf8bace02', 'Camara B4', 'rtsp://10.0.2.2:8554/camB4'),
('c2000000-0000-0000-0000-000000000005', 'e2831002-3b2c-4925-91b3-5efaf8bace02', 'Camara B5', 'rtsp://10.0.2.2:8554/camB5'),
('c2000000-0000-0000-0000-000000000006', 'e2831002-3b2c-4925-91b3-5efaf8bace02', 'Camara B6', 'rtsp://10.0.2.2:8554/camB6');

-- 7. Insert 12 mock camera events
INSERT INTO public.camera_events (camera_id, description) VALUES
('c1000000-0000-0000-0000-000000000001', 'Movimiento en A1'),
('c1000000-0000-0000-0000-000000000002', 'Movimiento en A2'),
('c1000000-0000-0000-0000-000000000003', 'Movimiento en A3'),
('c1000000-0000-0000-0000-000000000004', 'Movimiento en A4'),
('c1000000-0000-0000-0000-000000000005', 'Movimiento en A5'),
('c1000000-0000-0000-0000-000000000006', 'Movimiento en A6'),
('c2000000-0000-0000-0000-000000000001', 'Movimiento en B1'),
('c2000000-0000-0000-0000-000000000002', 'Movimiento en B2'),
('c2000000-0000-0000-0000-000000000003', 'Movimiento en B3'),
('c2000000-0000-0000-0000-000000000004', 'Movimiento en B4'),
('c2000000-0000-0000-0000-000000000005', 'Movimiento en B5'),
('c2000000-0000-0000-0000-000000000006', 'Movimiento en B6');

COMMIT;
