"""Fail closed before network/install when the reviewed OS patch manifest is altered."""
import json
from pathlib import Path
import runpy

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('issue',['foreign_host','traversal','invalid_hash','extra_package'])
def test_os_sources_reject_unreviewed_input(tmp_path,monkeypatch,issue):
    scripts=ROOT/'backend/scripts';monkeypatch.syspath_prepend(str(scripts))
    artifacts=runpy.run_path(str(scripts/'prepare_os_packages.py'))['artifacts']
    record=json.loads((ROOT/'docs/ai-vision/OS_PACKAGES_REVIEW.json').read_text())
    if issue=='foreign_host':record['packages'][0]['url']='https://unreviewed.invalid/pkg.deb'
    elif issue=='traversal':record['packages'][0]['filename']='../../outside.deb'
    elif issue=='invalid_hash':record['packages'][0]['sha256']='not-a-sha256'
    else:record['packages'].append(record['packages'][0].copy())
    target=tmp_path/'docs/ai-vision/OS_PACKAGES_REVIEW.json';target.parent.mkdir(parents=True);target.write_text(json.dumps(record))
    with pytest.raises(ValueError):artifacts(tmp_path)


def test_signed_index_tampering_is_rejected_before_install(tmp_path,monkeypatch):
    scripts=ROOT/'backend/scripts';monkeypatch.syspath_prepend(str(scripts))
    load=runpy.run_path(str(scripts/'prepare_os_packages.py'))['reviewed_index']
    record=json.loads((ROOT/'docs/ai-vision/OS_PACKAGES_REVIEW.json').read_text())
    payload=b'fake index';record['index']['bytes']=len(payload)
    target=tmp_path/'docs/ai-vision/OS_PACKAGES_REVIEW.json';target.parent.mkdir(parents=True);target.write_text(json.dumps(record))
    index=tmp_path/'backend/os-packages/APKINDEX.tar.gz';index.parent.mkdir(parents=True);index.write_bytes(payload)
    with pytest.raises(ValueError,match='signed index identity mismatch'):load(tmp_path)
