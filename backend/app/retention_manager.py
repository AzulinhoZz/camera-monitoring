import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from supabase import create_client

logger = logging.getLogger("retention_manager")

VALID_RETENTION_DAYS = [7, 15, 30, 90]
EVIDENCE_BUCKET = "motion-evidence"
CLIPS_BUCKET = "motion-clips"


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


class RetentionManager:

    def get_user_config(self, user_id: str) -> Dict[str, Any]:
        client = get_supabase_client()
        default_cfg = {"user_id": user_id, "retention_days": 30, "auto_cleanup_enabled": False}
        if not client:
            return default_cfg

        try:
            res = client.table("user_retention_configs").select("*").eq("user_id", user_id).execute()
            if res.data and len(res.data) > 0:
                row = res.data[0]
                return {
                    "user_id": user_id,
                    "retention_days": int(row.get("retention_days", 30)),
                    "auto_cleanup_enabled": bool(row.get("auto_cleanup_enabled", False)),
                }
            else:
                # Create default config row in Supabase
                client.table("user_retention_configs").upsert(default_cfg).execute()
                return default_cfg
        except Exception as e:
            logger.error(f"Failed to get user_retention_configs from Supabase for {user_id}: {e}")
            return default_cfg

    def set_user_config(self, user_id: str, retention_days: int, auto_cleanup_enabled: bool) -> Dict[str, Any]:
        if retention_days not in VALID_RETENTION_DAYS:
            raise ValueError(f"Días de retención inválidos. Opciones permitidas: {VALID_RETENTION_DAYS}")

        cfg = {
            "user_id": user_id,
            "retention_days": retention_days,
            "auto_cleanup_enabled": auto_cleanup_enabled,
        }

        client = get_supabase_client()
        if not client:
            raise RuntimeError("Database connection not available to save retention policy")

        try:
            res = client.table("user_retention_configs").upsert(cfg).execute()
            if not res.data:
                raise RuntimeError("Supabase rejected user_retention_configs save operation")
            return cfg
        except Exception as e:
            logger.error(f"Failed to set user_retention_configs in Supabase for {user_id}: {e}")
            raise RuntimeError(f"Error al guardar configuración de retención en Supabase: {str(e)}")

    def get_storage_stats(self, user_id: str) -> Dict[str, Any]:
        client = get_supabase_client()
        config = self.get_user_config(user_id)

        if not client:
            raise RuntimeError("Base de datos no disponible para consultar estadísticas")

        try:
            # 1. Fetch user's camera IDs
            cams_res = client.table("cameras").select("id").eq("user_id", user_id).execute()
            cam_ids = [c["id"] for c in (cams_res.data or [])]

            if not cam_ids:
                return {
                    "photos_count": 0,
                    "clips_count": 0,
                    "protected_events_count": 0,
                    "total_storage_mb": 0.0,
                    "calc_type": "exact",
                    "retention_days": config["retention_days"],
                    "auto_cleanup_enabled": config["auto_cleanup_enabled"],
                }

            # 2. Query camera events
            events_res = (
                client.table("camera_events")
                .select("id, evidence_path, clip_path, is_protected")
                .in_("camera_id", cam_ids)
                .execute()
            )

            photos_count = 0
            clips_count = 0
            protected_count = 0

            for ev in (events_res.data or []):
                if ev.get("evidence_path"):
                    photos_count += 1
                if ev.get("clip_path"):
                    clips_count += 1
                if ev.get("is_protected"):
                    protected_count += 1

            # 3. Calculate exact byte size from Supabase Storage metadata
            total_bytes = 0
            storage_query_success = False

            try:
                for cam_id in cam_ids:
                    prefix = f"{user_id}/{cam_id}"

                    # Evidence photos
                    try:
                        photo_files = client.storage.from_(EVIDENCE_BUCKET).list(prefix) or []
                        for f in photo_files:
                            if isinstance(f, dict):
                                meta = f.get("metadata") or {}
                                size = meta.get("size") if isinstance(meta, dict) else None
                                size = size or f.get("size", 0)
                                total_bytes += int(size)
                    except Exception:
                        pass

                    # Video clips
                    try:
                        clip_files = client.storage.from_(CLIPS_BUCKET).list(prefix) or []
                        for f in clip_files:
                            if isinstance(f, dict):
                                meta = f.get("metadata") or {}
                                size = meta.get("size") if isinstance(meta, dict) else None
                                size = size or f.get("size", 0)
                                total_bytes += int(size)
                    except Exception:
                        pass

                storage_query_success = True
            except Exception as st_err:
                logger.warning(f"Storage metadata size query failed for user {user_id}: {st_err}")

            if storage_query_success and total_bytes > 0:
                total_storage_mb = round(total_bytes / (1024.0 * 1024.0), 2)
                calc_type = "exact"
            else:
                # Fallback estimate based on photo/clip counts
                total_storage_mb = round((photos_count * 0.2) + (clips_count * 2.5), 2)
                calc_type = "estimated" if (photos_count > 0 or clips_count > 0) else "exact"

            return {
                "photos_count": photos_count,
                "clips_count": clips_count,
                "protected_events_count": protected_count,
                "total_storage_mb": total_storage_mb,
                "calc_type": calc_type,
                "retention_days": config["retention_days"],
                "auto_cleanup_enabled": config["auto_cleanup_enabled"],
            }

        except Exception as e:
            logger.error(f"Error getting storage stats for user {user_id}: {e}")
            raise RuntimeError(f"Error al consultar estadísticas de almacenamiento: {str(e)}")

    def set_event_protection(self, user_id: str, event_id: str, is_protected: bool) -> Dict[str, Any]:
        client = get_supabase_client()
        if not client:
            raise RuntimeError("Database connection not available")

        # 1. Verify event and camera ownership
        ev_res = client.table("camera_events").select("id, camera_id").eq("id", event_id).execute()
        if not ev_res.data:
            raise ValueError("Evento no encontrado")

        camera_id = ev_res.data[0]["camera_id"]
        cam_res = client.table("cameras").select("id").eq("id", camera_id).eq("user_id", user_id).execute()
        if not cam_res.data:
            raise PermissionError("No tiene permisos para modificar este evento")

        # 2. Update is_protected
        res = client.table("camera_events").update({"is_protected": is_protected}).eq("id", event_id).execute()
        if not res.data:
            raise RuntimeError("Error al actualizar estado de protección en Supabase")

        return {"event_id": event_id, "is_protected": is_protected}

    def cleanup_expired_evidence(
        self,
        user_id: str,
        dry_run: bool = True,
        is_auto_trigger: bool = False,
        batch_limit: int = 100
    ) -> Dict[str, Any]:
        client = get_supabase_client()
        config = self.get_user_config(user_id)
        retention_days = config["retention_days"]
        auto_cleanup_enabled = config["auto_cleanup_enabled"]

        # Rule 2: If automatic trigger and auto_cleanup_enabled is FALSE, abort!
        if is_auto_trigger and not auto_cleanup_enabled:
            logger.info(f"Auto cleanup disabled for user {user_id}. Skipping automatic purge.")
            return {
                "user_id": user_id,
                "dry_run": dry_run,
                "status": "aborted_disabled",
                "retention_days": retention_days,
                "deleted_photos": 0,
                "deleted_clips": 0,
                "freed_mb": 0.0,
            }

        if not client:
            raise RuntimeError("Database connection not available")

        try:
            cams_res = client.table("cameras").select("id").eq("user_id", user_id).execute()
            cam_ids = [c["id"] for c in (cams_res.data or [])]
            if not cam_ids:
                return {
                    "user_id": user_id,
                    "dry_run": dry_run,
                    "status": "completed",
                    "retention_days": retention_days,
                    "deleted_photos": 0,
                    "deleted_clips": 0,
                    "freed_mb": 0.0,
                }

            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days)
            cutoff_iso = cutoff_dt.isoformat()

            # Query expired, unprotected events that still have evidence_path or clip_path
            events_res = (
                client.table("camera_events")
                .select("id, camera_id, evidence_path, clip_path, is_protected")
                .in_("camera_id", cam_ids)
                .lt("detected_at", cutoff_iso)
                .eq("is_protected", False)
                .limit(batch_limit)
                .execute()
            )

            expired_events = events_res.data or []
            deleted_photos = 0
            deleted_clips = 0

            for ev in expired_events:
                ev_id = ev["id"]
                evidence_path = ev.get("evidence_path")
                clip_path = ev.get("clip_path")

                # Re-verify protection status right before deleting to prevent race conditions
                fresh_ev = client.table("camera_events").select("is_protected").eq("id", ev_id).execute()
                if fresh_ev.data and fresh_ev.data[0].get("is_protected", False):
                    logger.info(f"Event {ev_id} was protected concurrently. Skipping cleanup.")
                    continue

                # Process photo evidence deletion
                if evidence_path:
                    # Path ownership check: route must start with user_id
                    if not evidence_path.startswith(f"{user_id}/"):
                        logger.warning(f"Security Warning: evidence_path {evidence_path} does not belong to user {user_id}. Skipping.")
                    else:
                        deleted_photos += 1
                        if not dry_run:
                            try:
                                rem_res = client.storage.from_(EVIDENCE_BUCKET).remove([evidence_path])
                                # Verify storage removal result before setting path to NULL in DB
                                if isinstance(rem_res, list) and len(rem_res) > 0 and not rem_res[0].get("error"):
                                    client.table("camera_events").update({"evidence_path": None}).eq("id", ev_id).execute()
                                elif not isinstance(rem_res, list):
                                    # Fallback if remove returns response object
                                    client.table("camera_events").update({"evidence_path": None}).eq("id", ev_id).execute()
                            except Exception as e:
                                logger.error(f"Failed removing evidence file {evidence_path}: {e}")

                # Process video clip deletion
                if clip_path:
                    # Path ownership check: route must start with user_id
                    if not clip_path.startswith(f"{user_id}/"):
                        logger.warning(f"Security Warning: clip_path {clip_path} does not belong to user {user_id}. Skipping.")
                    else:
                        deleted_clips += 1
                        if not dry_run:
                            try:
                                rem_res = client.storage.from_(CLIPS_BUCKET).remove([clip_path])
                                # Verify storage removal result before setting path to NULL in DB
                                if isinstance(rem_res, list) and len(rem_res) > 0 and not rem_res[0].get("error"):
                                    client.table("camera_events").update({"clip_path": None}).eq("id", ev_id).execute()
                                elif not isinstance(rem_res, list):
                                    client.table("camera_events").update({"clip_path": None}).eq("id", ev_id).execute()
                            except Exception as e:
                                logger.error(f"Failed removing clip file {clip_path}: {e}")

            freed_mb = round((deleted_photos * 0.2) + (deleted_clips * 2.5), 2)
            logger.info(f"Cleanup for user {user_id} (dry_run={dry_run}): {deleted_photos} photos, {deleted_clips} clips, {freed_mb} MB freed")

            return {
                "user_id": user_id,
                "dry_run": dry_run,
                "status": "completed",
                "retention_days": retention_days,
                "deleted_photos": deleted_photos,
                "deleted_clips": deleted_clips,
                "freed_mb": freed_mb,
            }

        except Exception as e:
            logger.error(f"Error during retention cleanup for user {user_id}: {e}")
            raise RuntimeError(f"Error al ejecutar la limpieza de almacenamiento: {str(e)}")


retention_manager = RetentionManager()
