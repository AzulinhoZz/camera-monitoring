BEGIN;
CREATE TABLE public.camera_vision_configs (
 camera_id UUID PRIMARY KEY REFERENCES public.cameras(id) ON DELETE CASCADE,
 owner_id UUID NOT NULL,
 organization_id UUID,
 revision BIGINT NOT NULL CHECK (revision>0),
 rules JSONB NOT NULL CHECK (jsonb_typeof(rules)='array' AND jsonb_array_length(rules)<=32),
 last_events JSONB NOT NULL DEFAULT '{}',
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.camera_vision_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.camera_vision_configs FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.camera_vision_configs FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.camera_vision_configs TO authenticated;
GRANT ALL ON public.camera_vision_configs TO service_role;
CREATE POLICY vision_config_read ON public.camera_vision_configs FOR SELECT TO authenticated
 USING (EXISTS (SELECT 1 FROM public.cameras c WHERE c.id=camera_id
   AND c.user_id=owner_id AND c.organization_id IS NOT DISTINCT FROM camera_vision_configs.organization_id));
ALTER TABLE public.camera_events ADD COLUMN vision_metadata JSONB;

-- The API validates rule geometry; only its service credential may invoke writes.
-- Actor is taken from a verified session. Lock profiles before cameras/configs.
CREATE FUNCTION public.save_vision_config(p_actor_id UUID,p_camera_id UUID,p_revision BIGINT,p_rules JSONB)
RETURNS SETOF public.camera_vision_configs LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp AS $$
DECLARE actor public.profiles; cam public.cameras; cfg public.camera_vision_configs;
BEGIN
 SELECT * INTO actor FROM public.profiles WHERE id=p_actor_id FOR SHARE;
 SELECT * INTO cam FROM public.cameras WHERE id=p_camera_id FOR UPDATE;
 IF cam.id IS NULL OR p_actor_id IS NULL OR NOT COALESCE((cam.user_id=p_actor_id OR
   (actor.role='administrador_flota' AND actor.organization_id IS NOT NULL AND actor.organization_id=cam.organization_id)),false) THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Vision configuration denied';
 END IF;
 IF jsonb_typeof(p_rules) IS DISTINCT FROM 'array' OR jsonb_array_length(p_rules)>32 OR octet_length(p_rules::text)>60000 THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Invalid rules';
 END IF;
 IF EXISTS (SELECT 1 FROM jsonb_array_elements(p_rules) r WHERE
   r->>'camera_id' IS DISTINCT FROM cam.id::text OR r->>'owner_id' IS DISTINCT FROM cam.user_id::text OR
   (r->>'organization_id') IS DISTINCT FROM cam.organization_id::text) THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Rule scope denied';
 END IF;
 SELECT * INTO cfg FROM public.camera_vision_configs WHERE camera_id=p_camera_id;
 IF COALESCE(cfg.revision,0)<>p_revision THEN
   RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='Vision configuration conflict';
 END IF;
 RETURN QUERY INSERT INTO public.camera_vision_configs(camera_id,owner_id,organization_id,revision,rules)
 VALUES(cam.id,cam.user_id,cam.organization_id,p_revision+1,p_rules)
 ON CONFLICT(camera_id) DO UPDATE SET owner_id=EXCLUDED.owner_id,organization_id=EXCLUDED.organization_id,
 revision=EXCLUDED.revision,rules=EXCLUDED.rules,last_events=CASE WHEN camera_vision_configs.owner_id=EXCLUDED.owner_id AND camera_vision_configs.organization_id IS NOT DISTINCT FROM EXCLUDED.organization_id THEN (SELECT COALESCE(jsonb_object_agg(e.key,e.value),'{}'::jsonb) FROM jsonb_each(camera_vision_configs.last_events) e WHERE e.key IN (SELECT r->>'rule_id' FROM jsonb_array_elements(EXCLUDED.rules) r)) ELSE '{}'::jsonb END,updated_at=now() RETURNING *;
END; $$;

CREATE FUNCTION public.ingest_vision_event(p_event JSONB,p_revision BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE cam public.cameras; cfg public.camera_vision_configs; r JSONB; event_time TIMESTAMPTZ;
 event_id UUID; last_time TIMESTAMPTZ; rule_key TEXT;
BEGIN
 IF octet_length(p_event::text)>8000 THEN RAISE EXCEPTION 'Event too large'; END IF;
 SELECT * INTO cam FROM public.cameras WHERE id=(p_event->>'camera_id')::uuid FOR SHARE;
 SELECT * INTO cfg FROM public.camera_vision_configs WHERE camera_id=cam.id FOR UPDATE;
 IF cam.id IS NULL OR cfg.camera_id IS NULL OR cfg.revision<>p_revision OR
   cam.user_id::text IS DISTINCT FROM p_event->>'owner_id' OR
   cam.organization_id::text IS DISTINCT FROM p_event->>'organization_id' OR
   cfg.owner_id<>cam.user_id OR cfg.organization_id IS DISTINCT FROM cam.organization_id THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Vision event scope or revision denied';
 END IF;
 rule_key=p_event->>'rule_id';
 SELECT item INTO r FROM jsonb_array_elements(cfg.rules) item WHERE item->>'rule_id'=rule_key;
 IF r IS NULL OR (r->>'enabled')::boolean IS DISTINCT FROM true OR r->>'kind' IS DISTINCT FROM p_event->>'event_type' THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Vision rule disabled or absent';
 END IF;
 event_id=(p_event->>'event_id')::uuid;
 -- Replay never mutates reviewed/protected events and never reuploads media.
 IF EXISTS (SELECT 1 FROM public.camera_events WHERE id=event_id) THEN RETURN false; END IF;
 event_time=(p_event->>'timestamp')::timestamptz;
 IF event_time IS NULL OR event_time>now()+interval '30 seconds' OR event_time<now()-interval '5 minutes' THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Stale vision event';
 END IF;
 last_time=(cfg.last_events->>rule_key)::timestamptz;
 IF last_time IS NOT NULL AND (event_time<last_time OR event_time-last_time < make_interval(secs=>COALESCE((r->>'cooldown_seconds')::double precision,30))) THEN RETURN false; END IF;
 INSERT INTO public.camera_events(id,camera_id,event_type,description,detected_at,review_status,vision_metadata)
 VALUES(event_id,cam.id,'vision_'||(r->>'kind'),
   CASE WHEN r->>'kind'='probable_abandoned_object' THEN 'Posible objeto abandonado; requiere revisión humana' ELSE 'Regla de visión; requiere revisión humana' END,
   event_time,'pending',p_event || jsonb_build_object('config_revision',p_revision));
 UPDATE public.camera_vision_configs SET last_events=jsonb_set(last_events,ARRAY[rule_key],to_jsonb(event_time)) WHERE camera_id=cam.id;
 RETURN true;
END; $$;

-- Media is attached only to the original scope, with canonical owner/camera path.
CREATE FUNCTION public.attach_vision_media(p_event_id UUID,p_owner_id UUID,p_org_id UUID,p_kind TEXT,p_path TEXT)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE ev public.camera_events; cam public.cameras; expected TEXT;
BEGIN
 SELECT c.* INTO cam FROM public.cameras c JOIN public.camera_events e ON e.camera_id=c.id WHERE e.id=p_event_id FOR SHARE OF c;
 SELECT * INTO ev FROM public.camera_events WHERE id=p_event_id FOR UPDATE;
 IF ev.id IS NULL OR ev.vision_metadata IS NULL OR cam.user_id IS DISTINCT FROM p_owner_id OR
   cam.organization_id IS DISTINCT FROM p_org_id OR ev.vision_metadata->>'owner_id' IS DISTINCT FROM p_owner_id::text OR
   ev.vision_metadata->>'organization_id' IS DISTINCT FROM p_org_id::text THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Vision media scope denied';
 END IF;
 IF p_kind IS NULL OR p_kind NOT IN ('snapshot','clip') THEN RAISE EXCEPTION 'Invalid media kind'; END IF;
 IF p_path IS NULL THEN RETURN true; END IF;
 expected=p_owner_id::text||'/'||cam.id::text||'/'||p_event_id::text||CASE WHEN p_kind='snapshot' THEN '.jpg' ELSE '.mp4' END;
 IF p_path IS DISTINCT FROM expected THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Invalid media path'; END IF;
 IF p_kind='snapshot' THEN UPDATE public.camera_events SET evidence_path=p_path WHERE id=ev.id;
 ELSE UPDATE public.camera_events SET clip_path=p_path WHERE id=ev.id; END IF;
 RETURN true;
END; $$;
REVOKE ALL ON FUNCTION public.save_vision_config(UUID,UUID,BIGINT,JSONB),public.ingest_vision_event(JSONB,BIGINT),public.attach_vision_media(UUID,UUID,UUID,TEXT,TEXT) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.save_vision_config(UUID,UUID,BIGINT,JSONB),public.ingest_vision_event(JSONB,BIGINT),public.attach_vision_media(UUID,UUID,UUID,TEXT,TEXT) TO service_role;
COMMIT;
