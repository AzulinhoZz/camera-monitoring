"""Authentication failures must stop before scoped data, media or telemetry reads."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID
import os

import pytest
from fastapi.testclient import TestClient
from app import auth, vision_api
from app.main import app
from app.vision.dashboard import read_snapshot, write_snapshot
from app.tests.test_vision_dashboard import snapshot, SCOPE, NOW

CAMERA=str(UUID(int=1))
ROUTES=[f'/cameras/{CAMERA}/vision-status?preview=true',f'/cameras/{CAMERA}/vision-rules',
        '/events','/events/statistics',f'/events/{UUID(int=2)}/evidence',f'/events/{UUID(int=2)}/clip']


@pytest.mark.parametrize('route',ROUTES)
def test_anonymous_and_rejected_tokens_never_reach_data(monkeypatch,route):
    app.dependency_overrides.clear()
    data=Mock(side_effect=AssertionError('unauthenticated data access'))
    monkeypatch.setattr(vision_api,'get_client',data)
    invalid=Mock(side_effect=RuntimeError('provider error containing private diagnostics'))
    monkeypatch.setattr(auth,'create_client',lambda *args:SimpleNamespace(auth=SimpleNamespace(get_user=invalid)))
    client=TestClient(app)
    assert client.get(route).status_code in (401,403)
    response=client.get(route,headers={'Authorization':'Bearer rejected-fixture-token'})
    assert response.status_code==401 and 'private diagnostics' not in response.text
    data.assert_not_called()
    invalid.assert_called_once_with('rejected-fixture-token')


def test_dashboard_refuses_broadened_file_permissions(tmp_path):
    root=tmp_path/'private';write_snapshot(root,snapshot())
    file=root/f'{SCOPE.camera_id}.json'
    file.chmod(0o644)
    with pytest.raises(ValueError,match='private'):read_snapshot(root,SCOPE,now=NOW)
    file.chmod(0o600)
    assert read_snapshot(root,SCOPE,now=NOW).healthy
