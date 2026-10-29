"""Fetch only the reviewed Linux/Python3.12 wheel artifacts for offline Docker builds.

Works on any host: no downloaded code is executed. Metadata and hashes are
versioned in this repository. Never reads package indexes or credentials.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen


def locked_artifacts(root):
    reviews=json.loads((root/'docs/ai-vision/PHASE_6_PYTHON_REVIEW.json').read_text())['reviews']
    records={r['name']:(r['version'],r['wheel']) for r in reviews}
    tooling=json.loads((root/'docs/ai-vision/PHASE_6_TOOLING_REVIEW.json').read_text())
    records['pip']=(tooling['version'],{'filename':tooling['filename'],'url':tooling['url'],
        'size':tooling['bytes'],'digests':{'sha256':tooling['sha256']}})
    artifacts=[]
    for file in ('requirements-runtime.lock','requirements-tooling.lock'):
        for line in (root/'backend'/file).read_text().splitlines():
            if not line or line.startswith('#'):continue
            match=re.fullmatch(r'([a-z0-9-]+)==([^ ]+) --hash=sha256:([a-f0-9]{64})',line)
            if not match:raise ValueError('unsupported release lock syntax')
            name,version,digest=match.groups()
            reviewed,wheel=records[name]
            if version!=reviewed or digest!=wheel['digests']['sha256']:raise ValueError('lock/review mismatch')
            url=urlsplit(wheel['url'])
            if url.scheme!='https' or url.hostname!='files.pythonhosted.org' or url.username or url.password:
                raise ValueError('unexpected artifact source')
            filename=wheel['filename']
            if Path(filename).name!=filename or not filename.endswith('.whl'):raise ValueError('invalid artifact filename')
            if not 0<wheel['size']<=100*1024*1024:raise ValueError('artifact size budget')
            artifacts.append(wheel)
    return artifacts


def fetch(wheel,directory):
    path=directory/wheel['filename'];expected=wheel['digests']['sha256']
    if path.exists():
        if path.is_symlink() or path.stat().st_size!=wheel['size'] or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('existing wheel does not match reviewed artifact')
        return
    with tempfile.NamedTemporaryFile(dir=directory,delete=False) as temp:
        name=Path(temp.name)
        try:
            with urlopen(wheel['url'],timeout=45) as response:
                remaining=wheel['size'];digest=hashlib.sha256()
                while remaining:
                    chunk=response.read(min(1024*1024,remaining))
                    if not chunk:raise ValueError('truncated artifact')
                    temp.write(chunk);digest.update(chunk);remaining-=len(chunk)
                if response.read(1) or digest.hexdigest()!=expected:raise ValueError('artifact integrity mismatch')
            temp.flush();os.link(name,path)
        finally:name.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);args=p.parse_args()
    output=Path(args.output)
    if not output.is_absolute() or output.is_symlink():p.error('choose a private absolute directory')
    output.mkdir(parents=True,mode=0o700,exist_ok=True)
    if output.stat().st_uid!=os.getuid() or output.stat().st_mode&0o077:p.error('wheel directory must be private and owned by this UID')
    artifacts=locked_artifacts(Path(__file__).resolve().parents[2])
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda w:fetch(w,output),artifacts))
    print(json.dumps({'result':'PASS','verified_wheels':len(artifacts),'path':str(output)}))

if __name__=='__main__':main()
