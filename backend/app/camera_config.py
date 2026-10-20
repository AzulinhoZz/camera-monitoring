import json
import os
import logging
from typing import Dict, Any, Optional
from supabase import create_client

logger = logging.getLogger("camera_config")
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "camera_configs.json")


class CameraConfigStore:
    def __init__(self, file_path: str = CONFIG_FILE_PATH):
        self.file_path = file_path
        self._supabase_enabled = True

    def _get_supabase_client(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            return None
        try:
            return create_client(url, key)
        except Exception as e:
            logger.error(f"Error creating Supabase client: {e}")
            return None

    def _get_default(self) -> Dict[str, Any]:
        return {
            "motion_enabled": True,
            "min_area": 1500,
            "threshold": 25,
            "cooldown_seconds": 5.0,
        }

    def _load_json_fallback(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load JSON fallback: {e}")
        return {}

    def _save_json_fallback(self, configs: Dict[str, Dict[str, Any]]):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save JSON fallback: {e}")

    def get_config(self, camera_id: str) -> Dict[str, Any]:
        client = self._get_supabase_client()
        if client and self._supabase_enabled:
            try:
                res = (
                    client.table("camera_motion_configs")
                    .select("camera_id, motion_enabled, min_area, threshold, cooldown_seconds")
                    .eq("camera_id", camera_id)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    return {
                        "motion_enabled": bool(row.get("motion_enabled", True)),
                        "min_area": int(row.get("min_area", 1500)),
                        "threshold": int(row.get("threshold", 25)),
                        "cooldown_seconds": float(row.get("cooldown_seconds", 5.0)),
                    }
                else:
                    # Config row does not exist yet in Supabase -> insert default row
                    default_cfg = self._get_default()
                    self.set_config(
                        camera_id=camera_id,
                        motion_enabled=default_cfg["motion_enabled"],
                        min_area=default_cfg["min_area"],
                        threshold=default_cfg["threshold"],
                        cooldown_seconds=default_cfg["cooldown_seconds"],
                    )
                    return default_cfg
            except Exception as e:
                logger.warning(f"camera_motion_configs table in Supabase query failed: {e}. Using JSON store.")
                self._supabase_enabled = False

        # JSON Fallback
        configs = self._load_json_fallback()
        if camera_id in configs:
            cfg = configs[camera_id].copy()
            defaults = self._get_default()
            for k, v in defaults.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        return self._get_default()

    def set_config(
        self,
        camera_id: str,
        motion_enabled: bool = True,
        min_area: int = 1500,
        threshold: int = 25,
        cooldown_seconds: float = 5.0,
    ) -> Dict[str, Any]:
        cfg = {
            "motion_enabled": motion_enabled,
            "min_area": min_area,
            "threshold": threshold,
            "cooldown_seconds": cooldown_seconds,
        }

        client = self._get_supabase_client()
        if client and self._supabase_enabled:
            try:
                payload = {
                    "camera_id": camera_id,
                    "motion_enabled": motion_enabled,
                    "min_area": min_area,
                    "threshold": threshold,
                    "cooldown_seconds": float(cooldown_seconds),
                }
                res = client.table("camera_motion_configs").upsert(payload).execute()
                if res.data:
                    return cfg
            except Exception as e:
                logger.warning(f"Failed to upsert camera_motion_configs in Supabase: {e}")
                self._supabase_enabled = False

        # JSON Fallback
        configs = self._load_json_fallback()
        configs[camera_id] = cfg
        self._save_json_fallback(configs)
        return cfg

    def delete_config(self, camera_id: str):
        client = self._get_supabase_client()
        if client and self._supabase_enabled:
            try:
                client.table("camera_motion_configs").delete().eq("camera_id", camera_id).execute()
            except Exception as e:
                logger.warning(f"Failed to delete camera_motion_configs in Supabase: {e}")

        configs = self._load_json_fallback()
        if camera_id in configs:
            del configs[camera_id]
            self._save_json_fallback(configs)


config_store = CameraConfigStore()
