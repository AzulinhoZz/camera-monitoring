"""No advisory error or known affected package may produce a release lock."""
from pathlib import Path
import runpy
import pytest

MODULE=runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/release_inventory.py'))


@pytest.mark.parametrize('change',[
    {'error':'lookup failed'}, {'vulnerabilities':[{'id':'fixture-CVE'}]}, {'wheel':None},
])
def test_lock_is_withheld_on_incomplete_or_affected_review(change):
    row={'name':'fixture','version':'1','error':None,'vulnerabilities':[],
         'wheel':{'digests':{'sha256':'a'*64}}}
    row.update(change)
    with pytest.raises(ValueError):MODULE['lock_text']([row])


def test_lock_uses_verified_hash_and_excludes_installer_tooling():
    def row(name):return {'name':name,'version':'1','error':None,'vulnerabilities':[],
                         'wheel':{'digests':{'sha256':'a'*64}}}
    lock=MODULE['lock_text']([row('pip'),row('fixture')])
    assert 'fixture==1 --hash=sha256:'+'a'*64 in lock
    assert 'pip==' not in lock
