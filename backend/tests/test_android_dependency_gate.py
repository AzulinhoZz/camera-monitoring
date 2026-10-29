import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/scan_android_dependencies.py'


@pytest.mark.parametrize('issue',['mismatched_apk','invalid_inventory','empty_sbom'])
def test_android_scan_never_accepts_wrong_or_invalid_artifact_identity(tmp_path,issue):
    sbom=tmp_path/'bom.json';sbom.write_text(json.dumps({'bomFormat':'CycloneDX','components':[{'type':'library','purl':'pkg:maven/org.example/fixture@1'}]}))
    inventory=tmp_path/'inventory.json';inventory.write_text(json.dumps({'apk_sha256':'a'*64,'distinct_maven_artifacts':1}) if issue=='mismatched_apk' else '{}')
    apk=tmp_path/'fixture.apk';apk.write_bytes(b'fixture-not-an-apk')
    if issue=='empty_sbom':
        import hashlib
        inventory.write_text(json.dumps({'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'distinct_maven_artifacts':143}))
        sbom.write_text(json.dumps({'bomFormat':'CycloneDX','components':[]}))
    output=tmp_path/'result'
    result=subprocess.run([sys.executable,str(SCRIPT),'--sbom',str(sbom),'--inventory',str(inventory),'--apk',str(apk),'--cache',str(tmp_path/'cache'),'--output',str(output)],capture_output=True,text=True,timeout=10)
    assert result.returncode==1
    report=json.loads((output/'result.json').read_text())
    assert report['status']=='BLOCKED' and report['accepted'] is False and report['deploy_authorized'] is False
    assert not (tmp_path/'cache/grype').exists()
