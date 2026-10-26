BEGIN;

-- Migration: Add roles, organizations, transport units, camera access grants, and interactive alert review status
-- Description: Transactional, non-destructive migration for profiles table, cameras, and RLS policies. Uses triggers for OLD/NEW checks and SECURITY DEFINER helpers for RLS policies.

-- 1. Update existing public.profiles table schema without dropping or recreating
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'conductor' CHECK (role IN ('conductor', 'administrador_flota')),
ADD COLUMN IF NOT EXISTS organization_id UUID,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Ensure primary key on id if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'profiles_pkey'
    ) THEN
        ALTER TABLE public.profiles ADD PRIMARY KEY (id);
    END IF;
END $$;

-- 2. Create organizations table with UNIQUE constraint on name
CREATE TABLE IF NOT EXISTS public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Foreign key constraint for profiles.organization_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_profiles_organization'
    ) THEN
        ALTER TABLE public.profiles
        ADD CONSTRAINT fk_profiles_organization
        FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;

-- 3. Create transport_units table (combis / public transport vehicles)
CREATE TABLE IF NOT EXISTS public.transport_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    unit_number TEXT NOT NULL,
    plate_number TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add transport_unit_id and organization_id columns to public.cameras
ALTER TABLE public.cameras
ADD COLUMN IF NOT EXISTS transport_unit_id UUID REFERENCES public.transport_units(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;

-- 4. Create camera_access_grants table (explicit driver access)
CREATE TABLE IF NOT EXISTS public.camera_access_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES public.cameras(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    granted_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(camera_id, user_id)
);

-- 5. Add review_status column to camera_events (for interactive motion alerts)
ALTER TABLE public.camera_events
ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'reviewed_ok', 'help_requested')),
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- 6. Backfill profiles for existing 3 users in auth.users
INSERT INTO public.profiles (id, full_name, role)
SELECT
    id,
    COALESCE(raw_user_meta_data->>'full_name', 'Conductor'),
    'conductor'
FROM auth.users
ON CONFLICT (id) DO UPDATE
SET full_name = COALESCE(public.profiles.full_name, EXCLUDED.full_name);

-- 7. RECURSION-FREE HELPER FUNCTIONS FOR RLS POLICIES
CREATE OR REPLACE FUNCTION public.get_auth_user_organization_id()
RETURNS UUID
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT organization_id FROM public.profiles WHERE id = auth.uid();
$$;

CREATE OR REPLACE FUNCTION public.get_auth_user_role()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT role FROM public.profiles WHERE id = auth.uid();
$$;

CREATE OR REPLACE FUNCTION public.has_camera_grant_access(p_camera_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.camera_access_grants
    WHERE camera_id = p_camera_id AND user_id = auth.uid()
  );
$$;

CREATE OR REPLACE FUNCTION public.get_camera_organization_id(p_camera_id UUID)
RETURNS UUID
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT organization_id FROM public.cameras WHERE id = p_camera_id;
$$;

REVOKE ALL ON FUNCTION public.get_auth_user_organization_id() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.get_auth_user_role() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.has_camera_grant_access(UUID) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.get_camera_organization_id(UUID) FROM PUBLIC, anon;

-- 8. Enable Row Level Security (RLS) on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transport_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.camera_access_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.camera_events ENABLE ROW LEVEL SECURITY;

-- 9. REPLACE LEGACY POLICIES SAFELY IN THE SAME TRANSACTION
DROP POLICY IF EXISTS "Users manage own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users manage own cameras" ON public.cameras;
DROP POLICY IF EXISTS "Users read own camera events" ON public.camera_events;

-- RLS POLICIES FOR PROFILES (Using helper function to avoid infinite policy recursion)
DROP POLICY IF EXISTS "Users can view own profile or org profile" ON public.profiles;
CREATE POLICY "Users can view own profile or org profile"
ON public.profiles FOR SELECT
USING (
    auth.uid() = id
    OR (
        organization_id IS NOT NULL
        AND organization_id = public.get_auth_user_organization_id()
    )
);

DROP POLICY IF EXISTS "Users can update own full_name only" ON public.profiles;
CREATE POLICY "Users can update own full_name only"
ON public.profiles FOR UPDATE
USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);

-- TRIGGER TO PREVENT ROLE AND ORGANIZATION SELF-ESCALATION BY REGULAR USERS
CREATE OR REPLACE FUNCTION public.prevent_profile_role_escalation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  IF (NEW.role IS DISTINCT FROM OLD.role) OR (NEW.organization_id IS DISTINCT FROM OLD.organization_id) THEN
    IF (current_setting('role', true) <> 'service_role' AND current_setting('role', true) <> 'postgres') THEN
      RAISE EXCEPTION 'Acceso denegado: No tiene permisos para modificar el rol o la organización del perfil.';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tr_prevent_profile_role_escalation ON public.profiles;
CREATE TRIGGER tr_prevent_profile_role_escalation
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.prevent_profile_role_escalation();

-- RLS POLICIES FOR ORGANIZATIONS
DROP POLICY IF EXISTS "Members can view own organization" ON public.organizations;
CREATE POLICY "Members can view own organization"
ON public.organizations FOR SELECT
USING (
    id = public.get_auth_user_organization_id()
);

DROP POLICY IF EXISTS "Fleet admins can update own organization" ON public.organizations;
CREATE POLICY "Fleet admins can update own organization"
ON public.organizations FOR UPDATE
USING (
    id = public.get_auth_user_organization_id()
    AND public.get_auth_user_role() = 'administrador_flota'
)
WITH CHECK (
    id = public.get_auth_user_organization_id()
    AND public.get_auth_user_role() = 'administrador_flota'
);

-- RLS POLICIES FOR TRANSPORT UNITS
DROP POLICY IF EXISTS "Org members can view transport units" ON public.transport_units;
CREATE POLICY "Org members can view transport units"
ON public.transport_units FOR SELECT
USING (
    organization_id = public.get_auth_user_organization_id()
);

DROP POLICY IF EXISTS "Fleet admins can manage transport units" ON public.transport_units;
CREATE POLICY "Fleet admins can manage transport units"
ON public.transport_units FOR ALL
USING (
    organization_id = public.get_auth_user_organization_id()
    AND public.get_auth_user_role() = 'administrador_flota'
)
WITH CHECK (
    organization_id = public.get_auth_user_organization_id()
    AND public.get_auth_user_role() = 'administrador_flota'
);

-- RLS POLICIES FOR CAMERA ACCESS GRANTS
DROP POLICY IF EXISTS "Users or org admins can view camera access grants" ON public.camera_access_grants;
CREATE POLICY "Users or org admins can view camera access grants"
ON public.camera_access_grants FOR SELECT
USING (
    user_id = auth.uid()
    OR (
        public.get_auth_user_role() = 'administrador_flota'
        AND public.get_camera_organization_id(camera_id) = public.get_auth_user_organization_id()
    )
);

DROP POLICY IF EXISTS "Fleet admins can manage camera access grants in same org" ON public.camera_access_grants;
CREATE POLICY "Fleet admins can manage camera access grants in same org"
ON public.camera_access_grants FOR ALL
USING (
    public.get_auth_user_role() = 'administrador_flota'
    AND public.get_camera_organization_id(camera_id) = public.get_auth_user_organization_id()
)
WITH CHECK (
    public.get_auth_user_role() = 'administrador_flota'
    AND public.get_camera_organization_id(camera_id) = public.get_auth_user_organization_id()
    AND EXISTS (
        SELECT 1 FROM public.profiles target_driver
        WHERE target_driver.id = public.camera_access_grants.user_id
        AND target_driver.organization_id = public.get_auth_user_organization_id()
    )
);

-- RLS POLICIES FOR CAMERAS
DROP POLICY IF EXISTS "Users can view authorized cameras" ON public.cameras;
CREATE POLICY "Users can view authorized cameras"
ON public.cameras FOR SELECT
USING (
    user_id = auth.uid()
    OR public.has_camera_grant_access(id)
    OR (
        public.get_auth_user_role() = 'administrador_flota'
        AND organization_id IS NOT NULL
        AND organization_id = public.get_auth_user_organization_id()
    )
);

DROP POLICY IF EXISTS "Users can insert own cameras" ON public.cameras;
CREATE POLICY "Users can insert own cameras"
ON public.cameras FOR INSERT
WITH CHECK (
    user_id = auth.uid()
    AND (
        organization_id IS NULL
        OR organization_id = public.get_auth_user_organization_id()
    )
);

DROP POLICY IF EXISTS "Users can update authorized cameras" ON public.cameras;
CREATE POLICY "Users can update authorized cameras"
ON public.cameras FOR UPDATE
USING (
    user_id = auth.uid()
    OR (
        public.get_auth_user_role() = 'administrador_flota'
        AND organization_id IS NOT NULL
        AND organization_id = public.get_auth_user_organization_id()
    )
)
WITH CHECK (
    user_id = auth.uid()
    OR (
        public.get_auth_user_role() = 'administrador_flota'
        AND organization_id IS NOT NULL
        AND organization_id = public.get_auth_user_organization_id()
    )
);

DROP POLICY IF EXISTS "Users can delete own cameras" ON public.cameras;
CREATE POLICY "Users can delete own cameras"
ON public.cameras FOR DELETE
USING (
    user_id = auth.uid()
    OR (
        public.get_auth_user_role() = 'administrador_flota'
        AND organization_id IS NOT NULL
        AND organization_id = public.get_auth_user_organization_id()
    )
);

-- TRIGGER TO PREVENT CAMERA OWNERSHIP, ORGANIZATION AND UNMATCHED TRANSPORT UNIT TAMPERING
CREATE OR REPLACE FUNCTION public.prevent_camera_ownership_tampering()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  -- Prevent changing camera user_id or organization_id by regular users
  IF (NEW.user_id IS DISTINCT FROM OLD.user_id) OR (NEW.organization_id IS DISTINCT FROM OLD.organization_id) THEN
    IF (current_setting('role', true) <> 'service_role' AND current_setting('role', true) <> 'postgres') THEN
      RAISE EXCEPTION 'Acceso denegado: No tiene permisos para cambiar la propiedad u organización de la cámara.';
    END IF;
  END IF;

  -- Validate that transport_unit_id belongs to the same organization as the camera if assigned
  IF NEW.transport_unit_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.transport_units tu
      WHERE tu.id = NEW.transport_unit_id
      AND tu.organization_id IS NOT DISTINCT FROM NEW.organization_id
    ) THEN
      RAISE EXCEPTION 'Acceso denegado: La unidad de transporte debe pertenecer a la misma organización de la cámara.';
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tr_prevent_camera_ownership_tampering ON public.cameras;
CREATE TRIGGER tr_prevent_camera_ownership_tampering
  BEFORE UPDATE ON public.cameras
  FOR EACH ROW
  EXECUTE FUNCTION public.prevent_camera_ownership_tampering();

-- RLS POLICIES FOR CAMERA EVENTS
DROP POLICY IF EXISTS "Users can view authorized camera events" ON public.camera_events;
CREATE POLICY "Users can view authorized camera events"
ON public.camera_events FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM public.cameras c
        WHERE c.id = public.camera_events.camera_id
        AND (
            c.user_id = auth.uid()
            OR public.has_camera_grant_access(c.id)
            OR (
                public.get_auth_user_role() = 'administrador_flota'
                AND c.organization_id IS NOT NULL
                AND c.organization_id = public.get_auth_user_organization_id()
            )
        )
    )
);

-- AUTOMATIC PROFILE CREATION TRIGGER ON NEW USER SIGNUP
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', 'Conductor'),
    'conductor'
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

-- Revoke execution privileges from public/anon to secure function
REVOKE ALL ON FUNCTION public.handle_new_user() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.handle_new_user() FROM anon;
REVOKE ALL ON FUNCTION public.handle_new_user() FROM authenticated;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

COMMIT;
