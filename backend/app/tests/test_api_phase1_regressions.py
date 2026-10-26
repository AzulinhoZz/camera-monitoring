"""Strict select/filter fakes expose bugs hidden by unconstrained MagicMock rows."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import admin, cameras, events, permissions
from app.auth import get_current_user
from app.main import app


class Query:
    def __init__(self, database, table):
        self.database, self.table = database, table
        self.columns = "*"
        self.filters = []
        self.write = None

    def select(self, columns, **kwargs):
        self.columns = columns
        return self

    def eq(self, key, value):
        self.filters.append(lambda row: row.get(key) == value)
        return self

    def in_(self, key, values):
        self.filters.append(lambda row: row.get(key) in values)
        return self

    def order(self, *args, **kwargs): return self
    def limit(self, *args, **kwargs): return self

    def upsert(self, row):
        self.write = row
        return self

    def update(self, row):
        self.write = row
        return self

    def execute(self):
        if self.write is not None:
            self.database.writes.append((self.table, self.write))
            if self.database.fail_writes:
                raise RuntimeError("synthetic persistence failure")
            return SimpleNamespace(data=[self.write])
        rows = [r for r in self.database.rows.get(self.table, []) if all(f(r) for f in self.filters)]
        if self.columns != "*":
            columns = {c.strip() for c in self.columns.split(",")}
            rows = [{k: v for k, v in row.items() if k in columns} for row in rows]
        return SimpleNamespace(data=rows)


class Database:
    def __init__(self):
        self.rows = {
            "cameras": [{"id": "cam-a", "user_id": "owner", "organization_id": "org-a",
                         "name": "Synthetic", "rtsp_url": "rtsp://source.invalid/live"}],
            "camera_events": [{"id": "event-a", "camera_id": "cam-a", "event_type": "motion_detected",
                               "description": "synthetic", "detected_at": "2026-10-26T20:00:00Z",
                               "evidence_path": "owner/cam-a/event-a.jpg", "clip_path": "owner/cam-a/event-a.mp4",
                               "is_protected": True, "review_status": "reviewed_ok", "reviewed_at": "2026-10-26T20:01:00Z"}],
            "profiles": [{"id": "recipient", "organization_id": "org-a"}],
            "camera_access_grants": [{"id": "grant", "camera_id": "cam-a", "user_id": "reader"}],
        }
        self.writes = []
        self.fail_writes = False
        self.storage = self
        self.signed_paths = []

    def table(self, name): return Query(self, name)
    def from_(self, name): return self

    def create_signed_url(self, path, ttl):
        self.signed_paths.append((path, ttl))
        return {"signedURL": "https://storage.invalid/synthetic"}


@pytest.fixture
def backend(monkeypatch):
    db = Database()
    for module in (cameras, events):
        monkeypatch.setattr(module, "create_client", lambda *args, **kwargs: db)
    monkeypatch.setattr(permissions, "get_supabase_client", lambda: db)
    monkeypatch.setattr(admin, "get_supabase_client", lambda: db)
    return db


def user(identity="owner", role="conductor", org="org-a"):
    return dict(id=identity, role=role, organization_id=org)


def as_user(value):
    app.dependency_overrides[get_current_user] = lambda: value
    return TestClient(app)


def test_stream_url_and_event_metadata_respect_projection(backend):
    client = as_user(user())
    stream = client.get("/cameras/cam-a/stream-url")
    assert stream.status_code == 200
    assert stream.json()["stream_path"] == "live"
    response = client.get("/events")
    assert response.status_code == 200
    row = response.json()["events"][0]
    assert row["has_evidence"] and row["has_clip"] and row["is_protected"]
    assert row["review_status"] == "reviewed_ok"
    assert row["reviewed_at"] is not None


@pytest.mark.parametrize("suffix,column", [("evidence", "evidence_path"), ("clip", "clip_path")])
def test_signed_media_present_absent_and_tenant_denied(backend, suffix, column):
    client = as_user(user())
    response = client.get(f"/events/event-a/{suffix}")
    assert response.status_code == 200
    assert response.json()["signed_url"] == "https://storage.invalid/synthetic"
    assert backend.signed_paths[-1] == (backend.rows["camera_events"][0][column], 1800)
    client = as_user(user("outsider", org="org-b"))
    previous = len(backend.signed_paths)
    assert client.get(f"/events/event-a/{suffix}").status_code == 403
    assert len(backend.signed_paths) == previous
    backend.rows["camera_events"][0][column] = None
    response = as_user(user()).get(f"/events/event-a/{suffix}")
    assert response.status_code == 200 and response.json()["signed_url"] is None


def test_admin_positive_access_and_cross_org_denial(backend):
    assert permissions.has_camera_access(user("fleet", "administrador_flota"), "cam-a")
    assert permissions.can_manage_camera(user("fleet", "administrador_flota"), "cam-a")
    assert not permissions.has_camera_access(user("fleet", "administrador_flota", "org-b"), "cam-a")
    assert not permissions.can_manage_camera(user("reader"), "cam-a")
    assert permissions.has_camera_access(user("reader"), "cam-a")


@pytest.mark.parametrize("method,path,payload", [
    ("put", "/cameras/cam-a", {"name": "changed"}),
    ("delete", "/cameras/cam-a", None),
    ("post", "/events", {"camera_id": "cam-a"}),
])
def test_read_grant_cannot_mutate_camera_or_create_event(backend, method, path, payload):
    client = as_user(user("reader"))
    response = getattr(client, method)(path, **({"json": payload} if payload is not None else {}))
    assert response.status_code in (403, 404)
    assert backend.writes == []


@pytest.mark.parametrize("target", ["camera", "recipient", "missing_org", "nonadmin"])
def test_grant_rejects_cross_org_missing_scope_and_nonadmin(backend, target):
    current = user("fleet", "administrador_flota")
    if target == "camera": backend.rows["cameras"][0]["organization_id"] = "org-b"
    if target == "recipient": backend.rows["profiles"][0]["organization_id"] = "org-b"
    if target == "missing_org": current["organization_id"] = None
    if target == "nonadmin": current["role"] = "conductor"
    response = as_user(current).post("/admin/camera-grants", json={"camera_id": "cam-a", "user_id": "recipient"})
    assert response.status_code == 403
    assert backend.writes == []


def test_grant_same_org_succeeds(backend):
    response = as_user(user("fleet", "administrador_flota")).post(
        "/admin/camera-grants", json={"camera_id": "cam-a", "user_id": "recipient"})
    assert response.status_code == 201
    assert backend.writes == [("camera_access_grants", dict(camera_id="cam-a", user_id="recipient", granted_by="fleet"))]


def test_review_persistence_failure_is_not_reported_as_success(backend):
    backend.fail_writes = True
    response = as_user(user()).post("/events/event-a/review", json={"review_status": "reviewed_ok"})
    assert response.status_code == 500
