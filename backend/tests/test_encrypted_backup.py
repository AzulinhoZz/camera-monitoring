import hashlib
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/encrypted_backup.py'
MODULE=runpy.run_path(str(SCRIPT))


@pytest.fixture
def fixture(tmp_path):
    root=tmp_path/'private';root.mkdir(mode=0o700)
    source=root/'input';source.mkdir(mode=0o700);(source/'db.dump').write_bytes(b'generated-fixture-not-a-real-dump')
    (source/'storage').mkdir();(source/'storage/clip.bin').write_bytes(b'fixture-media'*10000)
    key=root/'key';MODULE['create_key'](key)
    return root,source,key


def test_restore_in_new_process_keeps_bytes_and_never_overwrites(fixture):
    root,source,key=fixture;archive=root/'backup.enc';MODULE['encrypt'](source,key,archive)
    restored=root/'restored'
    result=subprocess.run([sys.executable,str(SCRIPT),'restore','--key-file',str(key),'--archive',str(archive),'--destination',str(restored)],capture_output=True,text=True)
    assert result.returncode==0 and 'PASS' in result.stdout
    assert (restored/'storage/clip.bin').read_bytes()==(source/'storage/clip.bin').read_bytes()
    assert key.stat().st_mode&0o777==0o600
    with pytest.raises((ValueError,OSError)):MODULE['restore'](archive,key,restored)
    with pytest.raises(OSError):MODULE['encrypt'](source,key,archive)


def test_tamper_never_publishes_destination(fixture):
    root,source,key=fixture;archive=root/'backup.enc';MODULE['encrypt'](source,key,archive)
    data=bytearray(archive.read_bytes());data[-20]^=1;archive.write_bytes(data)
    with pytest.raises(InvalidTag):MODULE['restore'](archive,key,root/'rejected')
    assert not (root/'rejected').exists()
    assert not list(root.glob('.camera-restore-*'))


def test_source_symlinks_key_inclusion_and_loose_key_permissions_are_denied(fixture):
    root,source,key=fixture
    (source/'key-link').symlink_to(key)
    with pytest.raises(ValueError):MODULE['encrypt'](source,key,root/'backup.enc')
    (source/'key-link').unlink();key.chmod(0o644)
    with pytest.raises(ValueError):MODULE['encrypt'](source,key,root/'backup.enc')


def test_key_inside_source_and_atomic_replacement_of_existing_directory_are_denied(fixture):
    root,source,key=fixture;inside=source/'in-source.key';MODULE['create_key'](inside)
    with pytest.raises(ValueError):MODULE['encrypt'](source,inside,root/'backup.enc')
    staged=root/'staged';staged.mkdir();(staged/'kept').write_bytes(b'kept')
    existing=root/'existing';existing.mkdir()
    with pytest.raises(OSError):MODULE['publish_directory'](staged,existing)
    assert (staged/'kept').read_bytes()==b'kept' and existing.exists()
