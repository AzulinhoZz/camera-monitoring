"""Prepare reviewed Wolfi archives and the frozen signed index for networkless installation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re

from prepare_release_wheels import fetch

REPOSITORY='https://apk.cgr.dev/chainguard'


def artifacts(root):
    review=json.loads((root/'docs/ai-vision/OS_PACKAGES_REVIEW.json').read_text());rows=review['packages']
    if (review.get('architecture')!='x86_64' or review.get('repository')!=REPOSITORY
            or len(rows)!=review.get('package_count') or len({r['package'] for r in rows})!=len(rows)):
        raise ValueError('unexpected OS patch set')
    result=[]
    for row in rows:
        name=row['filename']
        if (not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9+_.-]*',row['package'])
                or not re.fullmatch(r'[A-Za-z0-9+_.-]+',row['version'])
                or name!=row['package']+'-'+row['version']+'.apk'
                or row['url']!=REPOSITORY+'/x86_64/'+name
                or type(row['bytes']) is not int or not 0<row['bytes']<=64*1024*1024
                or not re.fullmatch('[a-f0-9]{64}',row['sha256'])):
            raise ValueError('unreviewed package source or identity')
        result.append({'filename':name,'url':row['url'],'size':row['bytes'],'digests':{'sha256':row['sha256']}})
    for name,version in review['roots'].items():
        if not any(row['package']==name and row['version']==version for row in rows):raise ValueError('missing root constraint')
    return result


def reviewed_index(root):
    review=json.loads((root/'docs/ai-vision/OS_PACKAGES_REVIEW.json').read_text())
    blob=(root/'backend/os-packages/APKINDEX.tar.gz').read_bytes();expected=review['index']
    if len(blob)!=expected['bytes'] or hashlib.sha256(blob).hexdigest()!=expected['sha256']:
        raise ValueError('signed index identity mismatch')
    return blob,expected


def private_directory(path):
    if not path.is_absolute() or path.is_symlink():raise ValueError('private absolute directory required')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.stat().st_uid!=os.getuid() or path.stat().st_mode&0o077:raise ValueError('directory must be private and owned')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output);private_directory(output);arch=output/'x86_64';private_directory(arch)
    root=Path(__file__).resolve().parents[2];rows=artifacts(root)
    review=json.loads((root/'docs/ai-vision/OS_PACKAGES_REVIEW.json').read_text());blob,expected=reviewed_index(root)
    target=arch/'APKINDEX.tar.gz'
    if target.exists() and (target.is_symlink() or target.read_bytes()!=blob):raise ValueError('cached index mismatch; choose a new private directory')
    if not target.exists():target.write_bytes(blob)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda row:fetch(row,arch),rows))
    world=''.join(row['package']+'='+row['version']+'\n' for row in review['packages']);(output/'world.txt').write_text(world)
    checks=[expected['sha256']+'  x86_64/APKINDEX.tar.gz',hashlib.sha256(world.encode()).hexdigest()+'  world.txt']
    checks.extend(row['digests']['sha256']+'  x86_64/'+row['filename'] for row in rows)
    (output/'SHA256SUMS').write_text('\n'.join(checks)+'\n')
    print(json.dumps({'result':'PASS','verified_packages':len(rows),'index_sha256':expected['sha256'],'limits':'Archive integrity only here; apk enforces upstream index authentication during offline installation.'}))


if __name__=='__main__':main()
