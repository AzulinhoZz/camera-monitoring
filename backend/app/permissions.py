import os
import logging
from typing import Dict, Any, List, Optional
from supabase import create_client

logger = logging.getLogger("permissions")


def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


def get_user_profile(user_id: str, email: str, metadata_name: Optional[str] = None) -> Dict[str, Any]:
    client = get_supabase_client()
    default_profile = {
        "id": user_id,
        "email": email,
        "full_name": metadata_name or "Conductor",
        "role": "conductor",
        "organization_id": None
    }
    if not client:
        return default_profile

    try:
        res = client.table("profiles").select("id, role, organization_id, full_name").eq("id", user_id).execute()
        if res.data and len(res.data) > 0:
            row = res.data[0]
            return {
                "id": user_id,
                "email": email,
                "full_name": row.get("full_name") or metadata_name or "Conductor",
                "role": row.get("role", "conductor"),
                "organization_id": row.get("organization_id"),
            }
        else:
            return default_profile
    except Exception as e:
        logger.warning(f"profiles table query in Supabase failed: {e}. Defaulting to conductor role.")
        return default_profile


def has_camera_access(user: Dict[str, Any], camera_id: str, *, allow_grants: bool = True) -> bool:
    client = get_supabase_client()
    if not client:
        return False

    user_id = user["id"]
    role = user.get("role", "conductor")
    org_id = user.get("organization_id")

    try:
        # 1. Direct owner check
        cam_res = client.table("cameras").select("id, user_id, organization_id").eq("id", camera_id).execute()
        if not cam_res.data:
            return False

        cam = cam_res.data[0]
        if cam.get("user_id") == user_id:
            return True

        # 2. Fleet Admin check
        if role == "administrador_flota" and org_id and cam.get("organization_id") == org_id:
            return True

        # Explicit grants confer read access, not camera administration.
        if not allow_grants or not org_id or cam.get("organization_id") != org_id:
            return False

        # 3. Explicit access grant check
        try:
            grant_res = client.table("camera_access_grants").select("id").eq("camera_id", camera_id).eq("user_id", user_id).execute()
            if grant_res.data and len(grant_res.data) > 0:
                return True
        except Exception:
            pass

        return False

    except Exception as e:
        logger.error(f"Error checking camera access for user {user_id} and camera {camera_id}: {e}")
        return False


def get_authorized_camera_ids(user: Dict[str, Any]) -> List[str]:
    client = get_supabase_client()
    if not client:
        return []

    user_id = user["id"]
    role = user.get("role", "conductor")
    org_id = user.get("organization_id")

    try:
        # Own cameras
        own_cams = client.table("cameras").select("id").eq("user_id", user_id).execute()
        ids = set(c["id"] for c in (own_cams.data or []))

        # Granted cameras
        try:
            grants = client.table("camera_access_grants").select("camera_id").eq("user_id", user_id).execute()
            granted_ids = [g["camera_id"] for g in (grants.data or [])]
            if granted_ids and org_id:
                scoped = client.table("cameras").select("id").in_("id", granted_ids).eq("organization_id", org_id).execute()
                ids.update(c["id"] for c in (scoped.data or []))
        except Exception:
            pass

        # Org cameras for fleet admin
        if role == "administrador_flota" and org_id:
            try:
                org_cams = client.table("cameras").select("id").eq("organization_id", org_id).execute()
                for c in (org_cams.data or []):
                    ids.add(c["id"])
            except Exception:
                pass

        return list(ids)

    except Exception as e:
        logger.error(f"Error fetching authorized camera IDs for user {user_id}: {e}")
        return []


def can_manage_camera(user: Dict[str, Any], camera_id: str) -> bool:
    """Only the owner or the camera organization's fleet admin may mutate it."""
    return has_camera_access(user, camera_id, allow_grants=False)
