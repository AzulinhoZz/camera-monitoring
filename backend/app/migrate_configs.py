import os
import json
import logging
from supabase import create_client

logger = logging.getLogger("migration")
logging.basicConfig(level=logging.INFO)

def run_migration():
    json_path = os.path.join(os.path.dirname(__file__), "camera_configs.json")
    backup_path = json_path + ".bak"

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        print("[MIGRATION ERROR] Supabase credentials not found in environment.")
        return False

    client = create_client(url, key)

    # 1. Verify if camera_motion_configs table exists in Supabase
    try:
        client.table("camera_motion_configs").select("camera_id").limit(1).execute()
        print("[MIGRATION CHECK] Table 'public.camera_motion_configs' EXISTS in Supabase!")
    except Exception as e:
        print(f"[MIGRATION NOTICE] Table 'public.camera_motion_configs' does NOT exist in Supabase yet.")
        print(f"[MIGRATION NOTICE] Please run 'backend/migrations/001_camera_motion_configs.sql' in Supabase SQL Editor first.")
        return False

    # 2. Backup camera_configs.json
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"[MIGRATION BACKUP] Backup created at: {backup_path}")
        except Exception as e:
            print(f"[MIGRATION ERROR] Failed to create backup: {e}")
            return False
    else:
        data = {}
        print("[MIGRATION NOTICE] No camera_configs.json file found to migrate.")

    # 3. Query existing valid cameras from Supabase
    cam_res = client.table("cameras").select("id").execute()
    valid_camera_ids = {c["id"] for c in (cam_res.data or [])}

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    # 4. Migrate each JSON config idempotently using upsert
    for camera_id, cfg in data.items():
        if camera_id not in valid_camera_ids:
            print(f"[MIGRATION SKIPPED] Camera ID {camera_id} no longer exists in Supabase.")
            skipped_count += 1
            continue

        try:
            payload = {
                "camera_id": camera_id,
                "motion_enabled": cfg.get("motion_enabled", True),
                "min_area": cfg.get("min_area", 1500),
                "threshold": cfg.get("threshold", 25),
                "cooldown_seconds": float(cfg.get("cooldown_seconds", 5.0)),
            }
            res = client.table("camera_motion_configs").upsert(payload).execute()
            if res.data:
                print(f"[MIGRATION SUCCESS] Migrated config for camera {camera_id}: {res.data[0]}")
                migrated_count += 1
            else:
                error_count += 1
        except Exception as e:
            print(f"[MIGRATION ERROR] Error migrating camera {camera_id}: {e}")
            error_count += 1

    # 5. Also ensure any camera in Supabase without a config gets a default row
    for cam_id in valid_camera_ids:
        if cam_id not in data:
            try:
                payload = {
                    "camera_id": cam_id,
                    "motion_enabled": True,
                    "min_area": 1500,
                    "threshold": 25,
                    "cooldown_seconds": 5.0,
                }
                client.table("camera_motion_configs").upsert(payload).execute()
                migrated_count += 1
            except Exception as e:
                print(f"[MIGRATION ERROR] Error creating default config for {cam_id}: {e}")

    print("================ MIGRATION REPORT ================")
    print(f"Migrated records: {migrated_count}")
    print(f"Skipped records:  {skipped_count}")
    print(f"Errors:           {error_count}")
    print("==================================================")

    return True

if __name__ == "__main__":
    run_migration()
