"""Review-pinned external scanners. A missing vulnerability DB is BLOCKED, never PASS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
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
        executable=cache/tool;executable.write_bytes(bundle.extractfile(member).read());executable.chmod(0o700)
    return executable


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',required=True);p.add_argument('--output',required=True);p.add_argument('--cache',required=True);a=p.parse_args()
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
