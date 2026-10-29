"""Review-pinned external scanners. A missing vulnerability DB is BLOCKED, never PASS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile
import tempfile
from urllib.request import urlopen


def acquire(record, cache):
    tool=record['tool'];version=record['version']
    if tool not in ('syft','grype'):raise ValueError('unapproved scanner')
    archive=cache/record['asset']
    if not archive.exists():
        url=f'https://github.com/anchore/{tool}/releases/download/v{version}/{record["asset"]}'
        with urlopen(url,timeout=45) as response:data=response.read(100*1024*1024+1)
        if len(data)>100*1024*1024 or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('scanner archive integrity')
        archive.write_bytes(data)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('scanner cache integrity')
    with tarfile.open(archive) as bundle:
        member=bundle.getmember(tool)
        if not member.isfile() or member.size>200*1024*1024:raise ValueError('scanner entry budget')
        executable=cache/tool
        # Atomic replacement permits another verified scanner process to finish
        # without ETXTBSY from truncating its currently executing inode.
        with tempfile.NamedTemporaryFile(dir=cache,delete=False) as temporary:
            staged=Path(temporary.name)
            try:
                temporary.write(bundle.extractfile(member).read());temporary.flush()
                staged.chmod(0o700);os.replace(staged,executable)
            finally:staged.unlink(missing_ok=True)
    return executable


def verify_database_archive(path, expected):
    """Integrity only: expected digest must come from trusted official metadata."""
    if not re.fullmatch(r'[a-f0-9]{64}',expected or ''):
        raise ValueError('official SHA-256 required')
    path=Path(path).resolve(strict=True)
    if not path.is_file() or not 0<path.stat().st_size<=1024*1024*1024:
        raise ValueError('database archive size/type')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    if digest.hexdigest()!=expected:raise ValueError('database archive integrity')
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',required=True);p.add_argument('--output',required=True);p.add_argument('--cache',required=True);p.add_argument('--db-archive');p.add_argument('--db-sha256');a=p.parse_args()
    if bool(a.db_archive)!=bool(a.db_sha256):p.error('--db-archive and official --db-sha256 are required together')
    if platform.system()!='Linux' or platform.machine()!='x86_64':p.error('reviewed scanners target Linux x86_64')
    output=Path(a.output);output.mkdir(parents=True,mode=0o700,exist_ok=True)
    cache=Path(a.cache);cache.mkdir(parents=True,mode=0o700,exist_ok=True)
    if cache.is_symlink() or cache.stat().st_uid!=os.getuid() or cache.stat().st_mode&0o077:p.error('scanner cache must be private and owned by this UID')
    archive=Path(a.archive).resolve(strict=True)
    records=json.loads((Path(__file__).resolve().parents[2]/'docs/ai-vision/PHASE_6_SCANNER_REVIEW.json').read_text())
    report={'inventory':'NOT_RUN','vulnerability_scan':'BLOCKED','accepted':False,'limits':'A scanner failure, missing DB or finding is never converted into clean acceptance.'}
    env=os.environ|{'SYFT_CHECK_FOR_APP_UPDATE':'false','GRYPE_CHECK_FOR_APP_UPDATE':'false',
        'XDG_CACHE_HOME':str(cache),'GRYPE_DB_CACHE_DIR':str(cache/'grype-db'),'GRYPE_DB_MAX_ALLOWED_BUILT_AGE':'72h'}
    try:
        executables={r['tool']:acquire(r,cache) for r in records}
        with (output/'syft.log').open('w') as log:
            subprocess.run([str(executables['syft']),'docker-archive:'+str(archive),'-o','cyclonedx-json='+str(output/'image.cdx.json')],env=env,stdout=log,stderr=log,timeout=180,check=True)
        report['inventory']='PASS'
        if a.db_archive:
            database=verify_database_archive(a.db_archive,a.db_sha256)
            env['GRYPE_DB_AUTO_UPDATE']='false'
            with (output/'db-import.log').open('w') as log:
                subprocess.run([str(executables['grype']),'db','import',str(database)],env=env,stdout=log,stderr=log,timeout=180,check=True)
            report['database_source']={'mode':'offline','sha256':a.db_sha256,'limits':'Integrity verified; official origin requires trusted out-of-band metadata.'}
        with (output/'grype.log').open('w') as log:
            result=subprocess.run([str(executables['grype']),'sbom:'+str(output/'image.cdx.json'),'-o','json','--file',str(output/'vulnerabilities.json')],env=env,stdout=log,stderr=log,timeout=180)
        if result.returncode==0:
            findings=json.loads((output/'vulnerabilities.json').read_text())
            if not isinstance(findings.get('matches'),list) or not isinstance(findings.get('descriptor',{}).get('db'),dict) or findings['descriptor']['db'].get('error'):
                raise ValueError('incomplete scanner result')
            count=len(findings['matches']);report.update(vulnerability_scan='PASS' if count==0 else 'FINDINGS',findings=count,accepted=count==0)
        else:report['reason']='Grype failed; inspect log and provide an accessible, fresh official DB. No clean result.'
    except Exception as exc:
        report['reason']=type(exc).__name__+': scanner execution incomplete'
    (output/'scan-status.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['accepted'] else 1

if __name__=='__main__':raise SystemExit(main())
