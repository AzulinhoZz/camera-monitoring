"""Reject unreviewed/ambiguous stdlib input before changing either module."""
import copy
import hashlib
from pathlib import Path
import runpy

import pytest

apply = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/apply_python_backports.py'))['apply']


def fixture(root):
    rows = []
    for name in ['poplib.py', 'http/client.py']:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('VALUE = 1\n')
        rows.append({'path': name,
                     'before_sha256': hashlib.sha256(b'VALUE = 1\n').hexdigest(),
                     'after_sha256': hashlib.sha256(b'VALUE = 2\n').hexdigest(),
                     'edits': [{'before': 'VALUE = 1\n', 'after': 'VALUE = 2\n'}]})
    return {'files': rows}


@pytest.mark.parametrize('issue', ['input_hash', 'output_hash', 'context', 'scope', 'symlink'])
def test_rejects_tampering_without_partial_write(tmp_path, issue):
    review = fixture(tmp_path)
    row = review['files'][1]
    if issue == 'input_hash':
        (tmp_path / row['path']).write_text('UNREVIEWED = 1\n')
    elif issue == 'output_hash':
        row['after_sha256'] = '0' * 64
    elif issue == 'context':
        row['edits'][0]['before'] = 'missing context'
    elif issue == 'scope':
        row['path'] = '../outside.py'
    else:
        path = tmp_path / row['path']
        path.unlink()
        path.symlink_to(tmp_path / 'poplib.py')
    with pytest.raises(ValueError):
        apply(tmp_path, review)
    assert (tmp_path / 'poplib.py').read_text() == 'VALUE = 1\n'


def test_reviewed_application_is_idempotent(tmp_path):
    review = fixture(tmp_path)
    unchanged = copy.deepcopy(review)
    assert apply(tmp_path, review)['modified_modules'] == 2
    assert apply(tmp_path, review)['modified_modules'] == 0
    assert review == unchanged
    assert (tmp_path / 'http/client.py').read_text() == 'VALUE = 2\n'


def test_unchecked_bytecode_caches_are_invalidated_even_if_source_already_patched(tmp_path):
    review = fixture(tmp_path)
    apply(tmp_path, review)
    cached = tmp_path / '__pycache__'
    cached.mkdir()
    target = cached / 'poplib.cpython-313.pyc'
    target.write_bytes(b'unchecked stale bytecode')
    unrelated = cached / 'unrelated.cpython-313.pyc'
    unrelated.write_bytes(b'keep')
    assert apply(tmp_path, review)['removed_bytecode_caches'] == 1
    assert not target.exists()
    assert unrelated.read_bytes() == b'keep'
