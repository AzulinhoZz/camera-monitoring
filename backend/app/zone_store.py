import os
import json
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client

logger = logging.getLogger("zone_store")


def validate_polygon(points: List[Dict[str, float]]) -> bool:
    """
    Validates polygon geometry:
    - Must have at least 3 points.
    - All coordinates x, y must be float numbers in range [0.0, 1.0].
    """
    if not isinstance(points, list) or len(points) < 3:
        return False

    for pt in points:
        if not isinstance(pt, dict) or "x" not in pt or "y" not in pt:
            return False
        try:
            x = float(pt["x"])
            y = float(pt["y"])
            if x < 0.0 or x > 1.0 or y < 0.0 or y > 1.0:
                return False
        except (ValueError, TypeError):
            return False

    return True


class ZoneStore:
    def __init__(self):
        self._local_zones: Dict[str, List[Dict[str, Any]]] = {}

    def _get_supabase_client(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            return None
        try:
            return create_client(url, key)
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {e}")
            return None

    def get_zones(self, camera_id: str) -> List[Dict[str, Any]]:
        client = self._get_supabase_client()
        if client:
            try:
                res = (
                    client.table("camera_detection_zones")
                    .select("id, camera_id, name, polygon_json, is_active")
                    .eq("camera_id", camera_id)
                    .eq("is_active", True)
                    .execute()
                )
                zones = []
                for row in (res.data or []):
                    poly = row.get("polygon_json")
                    if isinstance(poly, str):
                        poly = json.loads(poly)
                    zones.append({
                        "id": row["id"],
                        "camera_id": row["camera_id"],
                        "name": row.get("name", "Zona"),
                        "polygon": poly,
                        "is_active": row.get("is_active", True),
                    })
                return zones
            except Exception as e:
                logger.warning(f"Failed to query camera_detection_zones from Supabase: {e}. Using local store.")

        return self._local_zones.get(camera_id, [])

    def add_zone(self, camera_id: str, name: str, polygon: List[Dict[str, float]]) -> Dict[str, Any]:
        if not validate_polygon(polygon):
            raise ValueError("Polígono inválido. Se requieren al menos 3 puntos con coordenadas normalizadas entre 0.0 y 1.0.")

        client = self._get_supabase_client()
        if client:
            try:
                payload = {
                    "camera_id": camera_id,
                    "name": name.strip() or "Zona de Detección",
                    "polygon_json": polygon,
                    "is_active": True,
                }
                res = client.table("camera_detection_zones").insert(payload).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    return {
                        "id": row["id"],
                        "camera_id": row["camera_id"],
                        "name": row["name"],
                        "polygon": polygon,
                        "is_active": True,
                    }
            except Exception as e:
                logger.warning(f"Failed to insert zone into Supabase: {e}")

        # Local fallback
        import uuid
        new_zone = {
            "id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "name": name.strip() or "Zona de Detección",
            "polygon": polygon,
            "is_active": True,
        }
        if camera_id not in self._local_zones:
            self._local_zones[camera_id] = []
        self._local_zones[camera_id].append(new_zone)
        return new_zone

    def update_zone(self, camera_id: str, zone_id: str, name: Optional[str] = None, polygon: Optional[List[Dict[str, float]]] = None) -> Dict[str, Any]:
        if polygon is not None and not validate_polygon(polygon):
            raise ValueError("Polígono inválido. Se requieren al menos 3 puntos con coordenadas entre 0.0 y 1.0.")

        client = self._get_supabase_client()
        if client:
            try:
                update_payload = {}
                if name is not None:
                    update_payload["name"] = name.strip()
                if polygon is not None:
                    update_payload["polygon_json"] = polygon

                res = (
                    client.table("camera_detection_zones")
                    .update(update_payload)
                    .eq("id", zone_id)
                    .eq("camera_id", camera_id)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    return {
                        "id": row["id"],
                        "camera_id": row["camera_id"],
                        "name": row["name"],
                        "polygon": polygon or row.get("polygon_json"),
                        "is_active": True,
                    }
            except Exception as e:
                logger.warning(f"Failed to update zone in Supabase: {e}")

        # Local fallback
        zones = self.get_zones(camera_id)
        for z in zones:
            if z["id"] == zone_id:
                if name is not None:
                    z["name"] = name.strip()
                if polygon is not None:
                    z["polygon"] = polygon
                return z
        raise ValueError("Zona no encontrada")

    def delete_zone(self, camera_id: str, zone_id: str):
        client = self._get_supabase_client()
        if client:
            try:
                client.table("camera_detection_zones").delete().eq("id", zone_id).eq("camera_id", camera_id).execute()
            except Exception as e:
                logger.warning(f"Failed to delete zone from Supabase: {e}")

        if camera_id in self._local_zones:
            self._local_zones[camera_id] = [z for z in self._local_zones[camera_id] if z["id"] != zone_id]

    def clear_all_zones(self, camera_id: str):
        """Removes all custom zones for full frame detection mode."""
        client = self._get_supabase_client()
        if client:
            try:
                client.table("camera_detection_zones").delete().eq("camera_id", camera_id).execute()
            except Exception as e:
                logger.warning(f"Failed to clear zones from Supabase: {e}")

        if camera_id in self._local_zones:
            del self._local_zones[camera_id]


zone_store = ZoneStore()
