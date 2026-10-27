BEGIN;
-- Rollback removes only this migration's new RPC/privileges, never data.
-- It restores the known pre-010 helper privilege defect: do not run on live
-- systems without a reviewed application rollback/maintenance plan.
CREATE OR REPLACE FUNCTION public.has_camera_grant_access(p_camera_id UUID)
RETURNS BOOLEAN LANGUAGE sql SECURITY DEFINER STABLE
SET search_path = public, pg_temp
AS $$ SELECT EXISTS (SELECT 1 FROM public.camera_access_grants
 WHERE camera_id=p_camera_id AND user_id=auth.uid()); $$;
DROP FUNCTION IF EXISTS public.grant_camera_access_for_actor(UUID, UUID, UUID);
REVOKE EXECUTE ON FUNCTION public.get_auth_user_organization_id() FROM authenticated, service_role;
REVOKE EXECUTE ON FUNCTION public.get_auth_user_role() FROM authenticated, service_role;
REVOKE EXECUTE ON FUNCTION public.has_camera_grant_access(UUID) FROM authenticated, service_role;
REVOKE EXECUTE ON FUNCTION public.get_camera_organization_id(UUID) FROM authenticated, service_role;
COMMIT;
