from pathlib import Path
import json
import runpy
import pytest

ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/'backend/scripts'


def test_runtime_closure_preserves_extras_markers_and_cycles(monkeypatch):
    module=runpy.run_path(str(TOOLS/'build_runtime_lock.py'))
    metadata=module['metadata']
    monkeypatch.setattr(metadata,'version',lambda name:'1')
    requirements={'root':['base>=1','optional>=1; extra == "vision"','windows>=1; sys_platform == "win32"'], 'base':['root>=1'], 'optional':[]}
    monkeypatch.setattr(metadata,'requires',lambda name:requirements[name])
    assert module['runtime_names'](['root[vision]>=1'])=={'root','base','optional'}


def test_release_wheel_manifest_is_closed_and_hash_checked(tmp_path):
    module=runpy.run_path(str(TOOLS/'prepare_release_wheels.py'))
    artifacts=module['locked_artifacts'](ROOT)
    assert len(artifacts)==66 and len({w['filename'] for w in artifacts})==66
    wheel={'filename':'fixture.whl','size':1,'digests':{'sha256':'a'*64}}
    (tmp_path/'fixture.whl').write_bytes(b'x')
    with pytest.raises(ValueError):module['fetch'](wheel,tmp_path)


@pytest.mark.parametrize('missing',['image_vulnerability_scan','operator_approval','managed_staging'])
def test_release_cannot_pass_with_missing_or_blocked_gates(missing):
    module=runpy.run_path(str(TOOLS/'check_release_readiness.py'))
    gates={name:{'status':'PASS','evidence':'fixture'} for name in module['REQUIRED']}
    gates[missing]={'status':'BLOCKED','evidence':'fixture'}
    result=module['verdict']({'gates':gates,'image_id':'fixture','archive_sha256':'fixture'})
    assert result['decision']=='NO_GO' and missing in result['unresolved'] and result['deploy_authorized'] is False


def test_offline_database_rejects_mismatch_and_requires_trusted_digest(tmp_path):
    import hashlib
    verify=runpy.run_path(str(TOOLS/'scan_release_image.py'))['verify_database_archive']
    archive=tmp_path/'database.tar.zst';archive.write_bytes(b'fixture, not an actual database')
    with pytest.raises(ValueError):verify(archive,'a'*64)
    with pytest.raises(ValueError):verify(archive,'')
    assert verify(archive,hashlib.sha256(archive.read_bytes()).hexdigest())==archive.resolve()
