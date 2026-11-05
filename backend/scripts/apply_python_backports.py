"""Apply reviewed upstream stdlib backports only to exact source hashes.

Runs at offline image build time. Does not suppress version-based CVE matches.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sysconfig


def apply(root, review):
    root = Path(root).resolve(strict=True)
    pending = []
    caches = []
    rows = review['files']
    if {row['path'] for row in rows} != {'poplib.py', 'http/client.py'} or len(rows) != 2:
        raise ValueError('unexpected standard library patch scope')
    for row in rows:
        path = root / row['path']
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError('standard library path escapes root')
        cache_dir = path.parent / '__pycache__'
        if cache_dir.is_symlink():
            raise ValueError('standard library cache escapes root')
        for cache in cache_dir.glob(path.stem + '.*.pyc'):
            if cache.is_symlink() or not cache.resolve(strict=True).is_relative_to(root):
                raise ValueError('standard library cache escapes root')
            caches.append(cache)
        before = path.read_bytes()
        digest = hashlib.sha256(before).hexdigest()
        if digest == row['after_sha256']:
            continue
        if digest != row['before_sha256']:
            raise ValueError('unreviewed standard library source hash')
        after = before.decode('utf-8')
        for edit in row['edits']:
            if after.count(edit['before']) != 1:
                raise ValueError('ambiguous standard library patch context')
            after = after.replace(edit['before'], edit['after'])
        data = after.encode('utf-8')
        if hashlib.sha256(data).hexdigest() != row['after_sha256']:
            raise ValueError('patched standard library hash mismatch')
        compile(after, str(path), 'exec')
        pending.append((path, data))
    # Validate every input/output before making any file change.
    for path, data in pending:
        path.write_bytes(data)
    # Vendor bytecode uses unchecked hash caches (flags=1); -B alone still reads
    # those stale caches. Remove only caches of these two reviewed source modules.
    for cache in caches:
        cache.unlink()
    return {'result': 'PASS', 'modified_modules': len(pending),
            'removed_bytecode_caches': len(caches),
            'modules': [{'path': row['path'], 'sha256': row['after_sha256']} for row in rows],
            'limits': 'Source backports only; raw scanner matches retained. No release approval.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', required=True)
    parser.add_argument('--stdlib', default=sysconfig.get_path('stdlib'))
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    result = apply(args.stdlib, json.loads(Path(args.review).read_text()))
    Path(args.receipt).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
