BEGIN;
SET ROLE postgres;
INSERT INTO organizations(id,name) VALUES ('33333333-3333-3333-3333-333333333333','Vision org');
UPDATE cameras SET organization_id='33333333-3333-3333-3333-333333333333' WHERE id='c1000000-0000-0000-0000-000000000001';
UPDATE profiles SET organization_id='33333333-3333-3333-3333-333333333333';
SET ROLE service_role;
SELECT * FROM save_vision_config('f7210242-a53d-495b-a7d7-26f0e0313ca1','c1000000-0000-0000-0000-000000000001',0,
 '[{"rule_id":"44444444-4444-4444-4444-444444444444","camera_id":"c1000000-0000-0000-0000-000000000001","owner_id":"f7210242-a53d-495b-a7d7-26f0e0313ca1","organization_id":"33333333-3333-3333-3333-333333333333","kind":"intrusion","enabled":true,"cooldown_seconds":30}]');
DO $$
DECLARE e JSONB; accepted BOOLEAN;
BEGIN
 IF has_function_privilege('authenticated','save_vision_config(uuid,uuid,bigint,jsonb)','execute') OR
    has_function_privilege('anon','ingest_vision_event(jsonb,bigint)','execute') OR
    has_function_privilege('authenticated','attach_vision_media(uuid,uuid,uuid,text,text)','execute') THEN RAISE EXCEPTION 'RPC leak'; END IF;
 BEGIN
  PERFORM save_vision_config('e2831002-3b2c-4925-91b3-5efaf8bace02','c1000000-0000-0000-0000-000000000001',1,'[]');
  RAISE EXCEPTION 'nonowner write allowed';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM save_vision_config('f7210242-a53d-495b-a7d7-26f0e0313ca1','c1000000-0000-0000-0000-000000000001',0,'[]');
  RAISE EXCEPTION 'lost update allowed';
 EXCEPTION WHEN serialization_failure THEN NULL; END;
 e=jsonb_build_object('schema_version','1.0','event_id','55555555-5555-5555-5555-555555555555','camera_id','c1000000-0000-0000-0000-000000000001',
 'owner_id','f7210242-a53d-495b-a7d7-26f0e0313ca1','organization_id','33333333-3333-3333-3333-333333333333',
 'rule_id','44444444-4444-4444-4444-444444444444','event_type','intrusion','timestamp',now());
 IF NOT ingest_vision_event(e,1) THEN RAISE EXCEPTION 'valid event refused'; END IF;
 IF ingest_vision_event(e,1) THEN RAISE EXCEPTION 'duplicate accepted'; END IF;
 UPDATE camera_events SET review_status='reviewed_ok',is_protected=true WHERE id=(e->>'event_id')::uuid;
 IF ingest_vision_event(e,1) THEN RAISE EXCEPTION 'reviewed replay accepted'; END IF;
 IF NOT EXISTS(SELECT 1 FROM camera_events WHERE id=(e->>'event_id')::uuid AND is_protected AND review_status='reviewed_ok') THEN RAISE EXCEPTION 'replay mutated event'; END IF;
 IF ingest_vision_event(e||'{"event_id":"66666666-6666-6666-6666-666666666666"}',1) THEN RAISE EXCEPTION 'durable cooldown ignored'; END IF;
 BEGIN
  PERFORM ingest_vision_event(e||'{"owner_id":"e2831002-3b2c-4925-91b3-5efaf8bace02"}',1);
  RAISE EXCEPTION 'wrong owner accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM ingest_vision_event(e,2); RAISE EXCEPTION 'wrong revision accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM attach_vision_media((e->>'event_id')::uuid,(e->>'owner_id')::uuid,(e->>'organization_id')::uuid,'snapshot','other/path.jpg');
  RAISE EXCEPTION 'media path escape allowed';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 PERFORM attach_vision_media((e->>'event_id')::uuid,(e->>'owner_id')::uuid,(e->>'organization_id')::uuid,'snapshot',
 'f7210242-a53d-495b-a7d7-26f0e0313ca1/c1000000-0000-0000-0000-000000000001/55555555-5555-5555-5555-555555555555.jpg');
 PERFORM save_vision_config((e->>'owner_id')::uuid,(e->>'camera_id')::uuid,1,(SELECT rules FROM camera_vision_configs WHERE camera_id=(e->>'camera_id')::uuid));
 IF NOT EXISTS(SELECT 1 FROM camera_vision_configs WHERE revision=2 AND last_events ? (e->>'rule_id')) THEN RAISE EXCEPTION 'retained cooldown lost'; END IF;
 IF ingest_vision_event(e||'{"event_id":"88888888-8888-8888-8888-888888888888"}',2) THEN RAISE EXCEPTION 'config update reset cooldown'; END IF;
 PERFORM save_vision_config((e->>'owner_id')::uuid,(e->>'camera_id')::uuid,2,'[]');
 IF EXISTS(SELECT 1 FROM camera_vision_configs WHERE last_events<>'{}'::jsonb) THEN RAISE EXCEPTION 'removed rule cooldown leaked'; END IF;
END $$;
SET ROLE authenticated;
SET request.jwt.claim.sub='e2831002-3b2c-4925-91b3-5efaf8bace02';
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM camera_vision_configs) THEN RAISE EXCEPTION 'RLS leaked ungranted configuration'; END IF;
END $$;
SET ROLE postgres;
UPDATE cameras SET organization_id=NULL WHERE id='c1000000-0000-0000-0000-000000000001';
SET ROLE service_role;
DO $$ BEGIN
 BEGIN
  PERFORM attach_vision_media('55555555-5555-5555-5555-555555555555','f7210242-a53d-495b-a7d7-26f0e0313ca1','33333333-3333-3333-3333-333333333333','snapshot','x');
  RAISE EXCEPTION 'moved scope accepted media';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
ROLLBACK;
SELECT 'PASS: vision config permissions/RLS/revision, event idempotency/cooldown/review preservation and media scope';
