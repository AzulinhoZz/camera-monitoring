from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.vision.config import CameraConfig, WorkerConfig, checked_rtsp_url
from app.vision.contracts import CameraScope, DetectionEvent

CAMERA = "00000000-0000-0000-0000-000000000001"
OWNER = "00000000-0000-0000-0000-000000000002"
ORG = "00000000-0000-0000-0000-000000000003"


def event_data():
    return dict(camera_id=CAMERA, owner_id=OWNER, organization_id=ORG,
                event_id="00000000-0000-0000-0000-000000000004",
                worker_session_id="00000000-0000-0000-0000-000000000005",
                timestamp="2026-10-26T14:00:00-06:00", model_version="fixture:1",
                **{"class": "fixture_object"}, confidence=.8,
                bbox=dict(x_min=.1, y_min=.2, x_max=.5, y_max=.7), track_id=1)


def config(**kwargs):
    return CameraConfig(camera_id=CAMERA, owner_id=OWNER, **kwargs)


def test_event_roundtrip_and_utc():
    event = DetectionEvent(**event_data())
    assert event.timestamp == datetime(2026, 10, 26, 20, tzinfo=timezone.utc)
    assert event.timestamp.utcoffset() == timedelta(0)
    wire = event.model_dump_json(by_alias=True)
    assert '"class":"fixture_object"' in wire
    assert DetectionEvent.model_validate_json(wire) == event
    assert event.require_scope(CameraScope(camera_id=CAMERA, owner_id=OWNER, organization_id=ORG)) is event


@pytest.mark.parametrize("change", [
    {"confidence": float("nan")}, {"confidence": float("inf")}, {"confidence": 1.01},
    {"timestamp": "2026-10-26T20:00:00"}, {"schema_version": "2.0"},
    {"bbox": dict(x_min=.8, y_min=.2, x_max=.1, y_max=.7)},
    {"bbox": dict(x_min=-.1, y_min=.2, x_max=.5, y_max=.7)},
    {"track_id": -1}, {"unexpected": "value"},
])
def test_invalid_contracts_rejected(change):
    with pytest.raises(ValidationError):
        DetectionEvent(**(event_data() | change))


def test_scope_and_evidence_cannot_cross_tenants():
    data = event_data()
    data["evidence"] = {"bucket": "motion-evidence", "path": f"{OWNER}/{CAMERA}/fixture.jpg"}
    event = DetectionEvent(**data)
    for change in ({"organization_id": None}, {"owner_id": ORG}, {"camera_id": ORG}):
        with pytest.raises(ValueError, match="scope mismatch"):
            event.require_scope(CameraScope(camera_id=CAMERA, owner_id=OWNER, organization_id=ORG).model_copy(update={k: UUID(v) if v else None for k,v in change.items()}))
    for path in (f"{ORG}/{CAMERA}/fixture.jpg", f"{OWNER}/{CAMERA}/../secret", "https://signed.invalid/file?token=secret"):
        with pytest.raises(ValidationError):
            DetectionEvent(**(data | {"evidence": {"bucket": "motion-evidence", "path": path}}))


def test_personal_camera_scope_and_no_source_in_serialization():
    c = config(source_kind="rtsp", source="rtsp://private.invalid/camera")
    assert c.organization_id is None
    assert "private.invalid" not in repr(c)
    assert "private.invalid" not in c.model_dump_json()
    with pytest.raises(ValidationError):
        WorkerConfig(cameras=(c, c))
    with pytest.raises(ValidationError):
        config(capture_fps=3, recording_fps=10)
    with pytest.raises(ValidationError):
        config(source_kind="video", source="https://remote.invalid/video.mp4")


def resolved(monkeypatch, *addresses):
    monkeypatch.setattr("app.vision.config.socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (address, 554)) for address in addresses])


def test_rtsp_policy_resolves_and_pins_each_attempt(monkeypatch):
    resolved(monkeypatch, "10.42.0.7")
    c = config(source_kind="rtsp", source="rtsp://camera.internal:8554/live", allowed_cidrs=("10.42.0.0/24",))
    assert checked_rtsp_url(c) == "rtsp://10.42.0.7:8554/live"
    resolved(monkeypatch, "169.254.169.254")
    with pytest.raises(ValueError, match="denied"):
        checked_rtsp_url(c)


@pytest.mark.parametrize("url,address,cidrs", [
    ("rtsp://camera.invalid/live", "10.42.0.7", ()),
    ("rtsp://camera.invalid/live", "10.43.0.7", ("10.42.0.0/24",)),
    ("rtsp://camera.invalid/live", "169.254.169.254", ("0.0.0.0/0",)),
    ("rtsp://camera.invalid/live", "127.0.0.1", ("127.0.0.0/8",)),
    ("rtsp://secret:password@camera.invalid/live", "10.42.0.7", ("10.42.0.0/24",)),
    ("rtsp://camera.invalid/live?token=secret", "10.42.0.7", ("10.42.0.0/24",)),
    ("rtsps://camera.invalid/live", "10.42.0.7", ("10.42.0.0/24",)),
    ("http://camera.invalid/live", "10.42.0.7", ("10.42.0.0/24",)),
    ("rtsp://camera.invalid:22/live", "10.42.0.7", ("10.42.0.0/24",)),
])
def test_rtsp_policy_fails_closed_without_leaking_url(monkeypatch, url, address, cidrs):
    resolved(monkeypatch, address)
    c = config(source_kind="rtsp", source=url, allowed_cidrs=cidrs)
    with pytest.raises(ValueError) as error:
        checked_rtsp_url(c)
    assert str(error.value) == "RTSP source denied by server network policy"


def test_rtsp_mixed_dns_answer_denied(monkeypatch):
    resolved(monkeypatch, "10.42.0.7", "169.254.169.254")
    with pytest.raises(ValueError):
        checked_rtsp_url(config(source_kind="rtsp", source="rtsp://camera.invalid/live", allowed_cidrs=("0.0.0.0/0",)))


def test_operator_config_errors_hide_input_and_size_is_bounded(tmp_path, capsys):
    from app.vision.__main__ import main
    path = tmp_path / "invalid.json"
    path.write_text('{"cameras": [{"source": "rtsp://private:do-not-print@invalid/live"}]}')
    assert main(["--config", str(path), "--duration", "1"]) == 2
    output = capsys.readouterr()
    assert "do-not-print" not in output.err and "private" not in output.err
    path.write_text(" " * (64 * 1024 + 1))
    with pytest.raises(ValueError, match="size limit"):
        WorkerConfig.load(str(path))


def test_configuration_rejects_excessive_multicamera_frame_budget():
    cameras = tuple(CameraConfig(camera_id=UUID(int=i + 1), owner_id=OWNER,
                                 max_width=1280, max_height=720, queue_size=8) for i in range(4))
    with pytest.raises(ValidationError, match="64 MiB budget"):
        WorkerConfig(cameras=cameras)
