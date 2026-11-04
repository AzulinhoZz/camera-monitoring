import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock
from urllib.error import URLError

import pytest

spec = importlib.util.spec_from_file_location('staging_preflight', Path(__file__).resolve().parents[1] / 'scripts/staging_preflight.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
REF = 'a' * 20


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', f'https://{REF}.supabase.co')
    monkeypatch.setenv('SUPABASE_SECRET_KEY', 'synthetic-not-a-real-key')


def test_wrong_project_never_sends_credentials(configured, monkeypatch):
    network = MagicMock()
    monkeypatch.setattr(probe, 'build_opener', network)
    assert probe.probe('b' * 20)['status'] == 'BLOCKED'
    network.assert_not_called()


def test_transport_error_never_exposes_provider_details(configured, monkeypatch):
    opener = MagicMock()
    opener.open.side_effect = URLError('synthetic-not-a-real-key in private diagnostics')
    monkeypatch.setattr(probe, 'build_opener', lambda *args: opener)
    result = probe.probe(REF)
    assert result['status'] == 'BLOCKED' and not result['writes_performed']
    assert 'synthetic-not-a-real-key' not in json.dumps(result)
    assert opener.open.call_count == 1


def test_success_only_certifies_read_only_preflight(configured, monkeypatch):
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value.status = 200
    monkeypatch.setattr(probe, 'build_opener', lambda *args: opener)
    result = probe.probe(REF)
    assert result['status'] == 'PASS_PREFLIGHT_ONLY'
    assert not result['writes_performed'] and len(result['checks']) == 5
    for call in opener.open.call_args_list:
        request = call.args[0]
        assert request.get_method() == 'GET'
        assert request.data is None
        if '/rest/v1/' in request.full_url:
            assert 'limit=0' in request.full_url


def test_redirect_is_never_followed():
    assert probe.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid') is None
