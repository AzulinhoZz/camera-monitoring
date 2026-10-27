-- Maintenance-only rollback. Export configs/metadata first if they must be kept.
-- Existing event rows, media paths, reviews, protection and retention are preserved.
BEGIN;
DROP FUNCTION public.attach_vision_media(UUID,UUID,UUID,TEXT,TEXT);
DROP FUNCTION public.ingest_vision_event(JSONB,BIGINT);
DROP FUNCTION public.save_vision_config(UUID,UUID,BIGINT,JSONB);
DROP TABLE public.camera_vision_configs;
ALTER TABLE public.camera_events DROP COLUMN vision_metadata;
COMMIT;
