"""Read-only HTTPS staging contract probe; no users, rows or Storage objects are written."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a server credential to a redirect destination.


def probe(expected_project_ref):
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'status': 'BLOCKED',
              'writes_performed': False, 'checks': [],
              'limits': 'Read-only connectivity/schema probe, not Auth/RLS/Storage/device acceptance.'}
    base = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_SECRET_KEY', '')
    parsed = urlsplit(base)
    if (not re.fullmatch(r'[a-z0-9]{20}', expected_project_ref) or not key
            or parsed.scheme != 'https' or parsed.netloc != expected_project_ref + '.supabase.co'
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        report['reason'] = 'missing_configuration_or_target_mismatch'
        return report
    report['project_ref_sha256'] = hashlib.sha256(expected_project_ref.encode()).hexdigest()
    opener = build_opener(NoRedirect())
    checks = [('auth_settings', '/auth/v1/settings')]
    contracts = {
        'profiles': 'id,role,organization_id',
        'cameras': 'id,user_id,organization_id',
        'camera_events': 'id,camera_id,vision_metadata,review_status,is_protected',
        'camera_vision_configs': 'camera_id',
    }
    for table, columns in contracts.items():
        checks.append((table + '_contract', '/rest/v1/' + table + '?' + urlencode({'select': columns, 'limit': 0})))
    for name, path in checks:
        request = Request(base.rstrip('/') + path, headers={'apikey': key, 'Authorization': 'Bearer ' + key})
        try:
            with opener.open(request, timeout=20) as response:
                status = response.status
            report['checks'].append({'name': name, 'status': 'PASS' if status == 200 else 'FAIL', 'http_status': status})
        except HTTPError as error:
            report['checks'].append({'name': name, 'status': 'BLOCKED', 'http_status': error.code})
            break
        except (URLError, OSError):
            report['checks'].append({'name': name, 'status': 'BLOCKED', 'reason': 'transport_error'})
            break
    if len(report['checks']) == len(checks) and all(c['status'] == 'PASS' for c in report['checks']):
        report['status'] = 'PASS_PREFLIGHT_ONLY'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-project-ref', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = probe(args.expected_project_ref)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    output.chmod(0o600)
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS_PREFLIGHT_ONLY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
