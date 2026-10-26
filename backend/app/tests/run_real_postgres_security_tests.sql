-- Real PostgreSQL 15.19 RLS and Security Test Suite
-- Executed directly against isolated PostgreSQL test database camera_monitoring_test

\set ON_ERROR_STOP off

-- Create authenticated role if missing
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO authenticated, anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated, anon;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO authenticated, anon;

-- TEST 1: DATA PRESERVATION AUDIT
BEGIN;
SELECT '=== TEST 1: DATA PRESERVATION AUDIT ===' AS test_name;
SELECT COUNT(*) AS total_profiles FROM public.profiles;
SELECT COUNT(*) AS total_cameras FROM public.cameras;
SELECT COUNT(*) AS total_events FROM public.camera_events;
COMMIT;

-- TEST 2: DRIVER A CAMERA ISOLATION
BEGIN;
SET ROLE authenticated;
SET LOCAL request.jwt.claim.sub = 'f7210242-a53d-495b-a7d7-26f0e0313ca1';
SET LOCAL request.jwt.claim.role = 'authenticated';
SELECT '=== TEST 2: DRIVER A CAMERA ISOLATION ===' AS test_name;
SELECT id, name, user_id FROM public.cameras;
COMMIT;

-- TEST 3: DRIVER B CAMERA ISOLATION
BEGIN;
SET ROLE authenticated;
SET LOCAL request.jwt.claim.sub = 'e2831002-3b2c-4925-91b3-5efaf8bace02';
SET LOCAL request.jwt.claim.role = 'authenticated';
SELECT '=== TEST 3: DRIVER B CAMERA ISOLATION ===' AS test_name;
SELECT id, name, user_id FROM public.cameras;
COMMIT;

-- TEST 4: ROLE ESCALATION PREVENTION BY DRIVER A
BEGIN;
SET ROLE authenticated;
SET LOCAL request.jwt.claim.sub = 'f7210242-a53d-495b-a7d7-26f0e0313ca1';
SET LOCAL request.jwt.claim.role = 'authenticated';
SELECT '=== TEST 4: ROLE ESCALATION PREVENTION BY DRIVER A ===' AS test_name;
UPDATE public.profiles SET role = 'administrador_flota' WHERE id = 'f7210242-a53d-495b-a7d7-26f0e0313ca1';
ROLLBACK;

-- TEST 5: CAMERA OWNERSHIP TAMPERING PREVENTION
BEGIN;
SET ROLE authenticated;
SET LOCAL request.jwt.claim.sub = 'f7210242-a53d-495b-a7d7-26f0e0313ca1';
SET LOCAL request.jwt.claim.role = 'authenticated';
SELECT '=== TEST 5: CAMERA OWNERSHIP TAMPERING PREVENTION ===' AS test_name;
UPDATE public.cameras SET user_id = 'e2831002-3b2c-4925-91b3-5efaf8bace02' WHERE id = 'c1000000-0000-0000-0000-000000000001';
ROLLBACK;

-- TEST 6: CROSS-ORGANIZATION TRANSPORT UNIT REJECTION
BEGIN;
SET ROLE test_admin;
SELECT '=== TEST 6: CROSS-ORGANIZATION TRANSPORT UNIT REJECTION ===' AS test_name;

INSERT INTO public.organizations (id, name) VALUES
('11111111-1111-1111-1111-111111111111', 'Ruta 01 Test Org'),
('22222222-2222-2222-2222-222222222222', 'Ruta 02 Test Org')
ON CONFLICT (name) DO NOTHING;

INSERT INTO public.transport_units (id, organization_id, unit_number) VALUES
('33333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', 'Combi 99 Org 2')
ON CONFLICT DO NOTHING;

-- Set Camera A1 to Org 1
UPDATE public.cameras SET organization_id = '11111111-1111-1111-1111-111111111111' WHERE id = 'c1000000-0000-0000-0000-000000000001';

-- Attempt to assign Transport Unit from Org 2 to Camera in Org 1 -> Must fail!
UPDATE public.cameras SET transport_unit_id = '33333333-3333-3333-3333-333333333333' WHERE id = 'c1000000-0000-0000-0000-000000000001';
ROLLBACK;

-- TEST 7: EXPLICIT CAMERA ACCESS GRANT & DRIVER ISOLATION
BEGIN;
SET ROLE test_admin;
SELECT '=== TEST 7: EXPLICIT CAMERA ACCESS GRANT ===' AS test_name;
-- Grant Driver B access to Camera A1
INSERT INTO public.camera_access_grants (camera_id, user_id) VALUES ('c1000000-0000-0000-0000-000000000001', 'e2831002-3b2c-4925-91b3-5efaf8bace02') ON CONFLICT DO NOTHING;

-- Query cameras as Driver B -> Driver B now sees own 6 cameras + granted Camera A1!
SET ROLE authenticated;
SET LOCAL request.jwt.claim.sub = 'e2831002-3b2c-4925-91b3-5efaf8bace02';
SET LOCAL request.jwt.claim.role = 'authenticated';
SELECT id, name, user_id FROM public.cameras;
ROLLBACK;
