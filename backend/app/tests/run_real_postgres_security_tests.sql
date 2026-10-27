\set ON_ERROR_STOP on
-- ONLY after setup_test_db.sql and canonical 001..010 in a disposable database.
-- No blanket GRANT ON ALL FUNCTIONS: test the migration's actual privileges.
GRANT USAGE ON SCHEMA public, auth TO authenticated, anon, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated, service_role;
GRANT SELECT ON public.cameras TO anon;
BEGIN;
DO $$ BEGIN
 IF (SELECT count(*) FROM public.profiles)<>3 OR (SELECT count(*) FROM public.cameras)<>12
    OR (SELECT count(*) FROM public.camera_events)<>12 THEN RAISE EXCEPTION 'baseline data changed'; END IF;
 IF has_function_privilege('anon','public.get_auth_user_role()','EXECUTE') THEN RAISE EXCEPTION 'anon helper privilege'; END IF;
 IF has_function_privilege('authenticated','public.grant_camera_access_for_actor(uuid,uuid,uuid)','EXECUTE') THEN RAISE EXCEPTION 'public RPC privilege'; END IF;
END $$;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claim.sub='f7210242-a53d-495b-a7d7-26f0e0313ca1';
DO $$ BEGIN
 IF (SELECT count(*) FROM public.cameras)<>6 THEN RAISE EXCEPTION 'driver A isolation'; END IF;
 BEGIN
  UPDATE public.profiles SET role='administrador_flota' WHERE id=auth.uid();
  RAISE EXCEPTION USING ERRCODE='ZX001', MESSAGE='role escalation allowed';
 EXCEPTION WHEN SQLSTATE 'P0001' THEN NULL; END;
 BEGIN
  UPDATE public.cameras SET user_id='e2831002-3b2c-4925-91b3-5efaf8bace02' WHERE id='c1000000-0000-0000-0000-000000000001';
  RAISE EXCEPTION USING ERRCODE='ZX001', MESSAGE='ownership change allowed';
 EXCEPTION WHEN SQLSTATE 'P0001' THEN NULL; END;
 BEGIN
  PERFORM public.grant_camera_access_for_actor(auth.uid(),'c1000000-0000-0000-0000-000000000001',auth.uid());
  RAISE EXCEPTION USING ERRCODE='ZX001', MESSAGE='RPC executable by user';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
SET LOCAL request.jwt.claim.sub='e2831002-3b2c-4925-91b3-5efaf8bace02';
DO $$ BEGIN IF (SELECT count(*) FROM public.cameras)<>6 THEN RAISE EXCEPTION 'driver B isolation'; END IF; END $$;
SET LOCAL ROLE postgres;
INSERT INTO public.organizations(id,name) VALUES
 ('11111111-1111-1111-1111-111111111111','Synthetic A'),('22222222-2222-2222-2222-222222222222','Synthetic B');
UPDATE public.profiles SET organization_id='11111111-1111-1111-1111-111111111111';
UPDATE public.profiles SET role='administrador_flota' WHERE id='d3921003-4c3d-4925-91b3-5efaf8bace03';
UPDATE public.cameras SET organization_id='11111111-1111-1111-1111-111111111111' WHERE id='c1000000-0000-0000-0000-000000000001';
INSERT INTO public.transport_units(id,organization_id,unit_number) VALUES
 ('33333333-3333-3333-3333-333333333333','22222222-2222-2222-2222-222222222222','Synthetic unit');
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claim.sub='f7210242-a53d-495b-a7d7-26f0e0313ca1';
DO $$ BEGIN
 BEGIN
  UPDATE public.cameras SET transport_unit_id='33333333-3333-3333-3333-333333333333' WHERE id='c1000000-0000-0000-0000-000000000001';
  RAISE EXCEPTION USING ERRCODE='ZX001', MESSAGE='cross-org unit accepted';
 EXCEPTION WHEN SQLSTATE 'P0001' THEN
  IF SQLERRM NOT LIKE '%unidad de transporte%' THEN RAISE EXCEPTION 'wrong check failed: %',SQLERRM; END IF;
 END;
END $$;
SET LOCAL ROLE service_role;
SELECT public.grant_camera_access_for_actor('d3921003-4c3d-4925-91b3-5efaf8bace03','c1000000-0000-0000-0000-000000000001','e2831002-3b2c-4925-91b3-5efaf8bace02');
DO $$ BEGIN
 BEGIN
  PERFORM public.grant_camera_access_for_actor('f7210242-a53d-495b-a7d7-26f0e0313ca1','c1000000-0000-0000-0000-000000000001','e2831002-3b2c-4925-91b3-5efaf8bace02');
  RAISE EXCEPTION USING ERRCODE='ZX001', MESSAGE='conductor actor accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claim.sub='e2831002-3b2c-4925-91b3-5efaf8bace02';
DO $$ BEGIN IF (SELECT count(*) FROM public.cameras)<>7 THEN RAISE EXCEPTION 'valid grant not effective'; END IF; END $$;
SET LOCAL ROLE postgres;
UPDATE public.profiles SET organization_id='22222222-2222-2222-2222-222222222222' WHERE id='e2831002-3b2c-4925-91b3-5efaf8bace02';
SET LOCAL ROLE service_role;
DO $$ BEGIN
 BEGIN
  PERFORM public.grant_camera_access_for_actor('d3921003-4c3d-4925-91b3-5efaf8bace03','c1000000-0000-0000-0000-000000000001','e2831002-3b2c-4925-91b3-5efaf8bace02');
  RAISE EXCEPTION USING ERRCODE='ZX001', MESSAGE='cross-org recipient accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claim.sub='e2831002-3b2c-4925-91b3-5efaf8bace02';
DO $$ BEGIN IF (SELECT count(*) FROM public.cameras)<>6 THEN RAISE EXCEPTION 'stale grant still effective'; END IF; END $$;
ROLLBACK;
SELECT 'PASS: preservation, minimum privileges, isolation, escalation, unit check, atomic grants, stale-grant revocation' AS result;
