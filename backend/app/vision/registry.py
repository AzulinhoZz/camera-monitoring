"""Bind real RTSP configurations to camera scope/source fetched server-side."""
from uuid import UUID
import json, os
from pathlib import Path

from .config import WorkerConfig


def authorize_scopes(config: WorkerConfig, client):
    authorized = []
    for camera in config.cameras:
        if camera.source_kind != "rtsp":
            authorized.append(camera)
            continue
        result = client.table("cameras").select("id, user_id, organization_id, rtsp_url").eq("id", str(camera.camera_id)).execute()
        if len(result.data or []) != 1:
            raise ValueError("camera scope unavailable")
        row = result.data[0]
        org_id = UUID(row["organization_id"]) if row.get("organization_id") else None
        if UUID(row["user_id"]) != camera.owner_id or org_id != camera.organization_id:
            raise ValueError("camera scope changed or configuration mismatched")
        if camera.inference_source:
            if camera.inference_source==row['rtsp_url']:
                raise ValueError('substream duplicates original')
            # Approved operator registry is separate from client-controlled source fields.
            path=Path(os.environ['VISION_SUBSTREAM_REGISTRY'])
            if path.stat().st_size>65536:raise ValueError('substream registry budget')
            entries=json.loads(path.read_text())
            entry=entries.get(str(camera.camera_id),{})
            if (entry.get('owner_id')!=str(camera.owner_id) or entry.get('organization_id')!=(str(camera.organization_id) if camera.organization_id else None)
                    or entry.get('original')!=row['rtsp_url'] or entry.get('inference')!=camera.inference_source):
                raise ValueError('substream registry binding changed')
        authorized.append(camera.model_copy(update={"source": row["rtsp_url"]}))
    return WorkerConfig(cameras=tuple(authorized), metrics_interval_seconds=config.metrics_interval_seconds)
