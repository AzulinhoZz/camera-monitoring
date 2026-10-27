BEGIN;

-- Canonical migration directory: backend/migrations. No historical schema rewrite.
GRANT EXECUTE ON FUNCTION public.get_auth_user_organization_id() TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_auth_user_role() TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.has_camera_grant_access(UUID) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_camera_organization_id(UUID) TO authenticated, service_role;

-- A grant stops authorizing immediately if either party changes organization.
CREATE OR REPLACE FUNCTION public.has_camera_grant_access(p_camera_id UUID)
RETURNS BOOLEAN LANGUAGE sql SECURITY DEFINER STABLE
SET search_path = public, pg_temp
AS $$
 SELECT EXISTS (
   SELECT 1 FROM public.camera_access_grants g
   JOIN public.cameras c ON c.id = g.camera_id
   JOIN public.profiles p ON p.id = g.user_id
   WHERE g.camera_id = p_camera_id AND g.user_id = auth.uid()
     AND c.organization_id IS NOT NULL AND c.organization_id = p.organization_id
 );
$$;

-- Service-only RPC: the API supplies actor_id from its validated session, never
-- from a request body. Row locks keep scope stable until the grant is committed.
CREATE OR REPLACE FUNCTION public.grant_camera_access_for_actor(
    p_actor_id UUID, p_camera_id UUID, p_recipient_id UUID
) RETURNS SETOF public.camera_access_grants
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    actor_role TEXT;
    actor_org UUID;
    camera_org UUID;
    recipient_org UUID;
BEGIN
    -- Deterministic profile lock order avoids reciprocal-grant deadlocks.
    PERFORM id FROM public.profiles
      WHERE id IN (p_actor_id, p_recipient_id) ORDER BY id FOR SHARE;
    SELECT role, organization_id INTO actor_role, actor_org
      FROM public.profiles WHERE id = p_actor_id;
    SELECT organization_id INTO recipient_org FROM public.profiles WHERE id = p_recipient_id;
    SELECT organization_id INTO camera_org FROM public.cameras WHERE id = p_camera_id FOR SHARE;
    IF actor_role IS DISTINCT FROM 'administrador_flota' OR actor_org IS NULL
       OR camera_org IS DISTINCT FROM actor_org OR recipient_org IS DISTINCT FROM actor_org THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='Camera grant scope denied';
    END IF;
    RETURN QUERY INSERT INTO public.camera_access_grants(camera_id, user_id, granted_by)
      VALUES(p_camera_id, p_recipient_id, p_actor_id)
      ON CONFLICT(camera_id, user_id) DO UPDATE SET granted_by = EXCLUDED.granted_by
      RETURNING *;
END;
$$;
REVOKE ALL ON FUNCTION public.grant_camera_access_for_actor(UUID, UUID, UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.grant_camera_access_for_actor(UUID, UUID, UUID) TO service_role;
COMMIT;
