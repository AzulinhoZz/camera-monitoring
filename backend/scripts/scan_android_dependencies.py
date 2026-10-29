"""Reviewed Grype Maven snapshot tied to the actual APK; not native/device acceptance."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess

from scan_release_image import acquire,scanner_environment,verified_match_count


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sbom',required=True);p.add_argument('--inventory',required=True);p.add_argument('--apk',required=True);p.add_argument('--cache',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if platform.system()!='Linux' or platform.machine()!='x86_64':p.error('reviewed scanner targets Linux x86_64')
    cache=Path(a.cache);cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    if cache.is_symlink() or cache.stat().st_uid!=os.getuid() or cache.stat().st_mode&0o077:p.error('private owned scanner cache required')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True,mode=0o700)
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'status':'BLOCKED','accepted':False,'deploy_authorized':False,
        'scope':'Maven advisory matches from resolved graph; .so version/native analysis and device behavior not certified'}
    try:
        sbom=Path(a.sbom);inventory=Path(a.inventory);apk=Path(a.apk)
        if sbom.stat().st_size>16*1024*1024 or inventory.stat().st_size>2*1024*1024 or apk.stat().st_size>1024**3:raise ValueError('artifact budget')
        expected=json.loads(inventory.read_text());apk_sha=digest(apk)
        if apk_sha!=expected['apk_sha256']:raise ValueError('APK/inventory identity mismatch')
        report.update(apk_sha256=apk_sha,sbom_sha256=digest(sbom),inventory_sha256=digest(inventory))
        review=json.loads((Path(__file__).resolve().parents[2]/'docs/ai-vision/PHASE_6_SCANNER_REVIEW.json').read_text())
        tool=acquire(next(record for record in review if record['tool']=='grype'),cache)
        config=out/'grype-config.json';config.write_text(json.dumps({'ignore':[],'exclude':[],'ignore-wontfix':'','only-fixed':False,'only-notfixed':False,
            'check-for-app-update':False,'db':{'cache-dir':str(cache/'grype-db'),'validate-age':True,'max-allowed-built-age':'72h','validate-by-hash-on-start':True}}))
        with (out/'grype.log').open('wb') as log:
            result=subprocess.run([str(tool),'-c',str(config),'sbom:'+str(sbom),'-o','json','--file',str(out/'findings.json')],env=scanner_environment(cache),stdout=log,stderr=log,timeout=180)
        if result.returncode:raise RuntimeError('scanner failed')
        findings=json.loads((out/'findings.json').read_text());count=verified_match_count(findings)
        report.update(status='PASS_MAVEN_SNAPSHOT' if count==0 else 'FINDINGS',findings=count,accepted=count==0,database=findings['descriptor']['db']['status'])
    except Exception as error:report['reason']=type(error).__name__+': dependency scan incomplete'
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    return 0 if report['accepted'] else 1

if __name__=='__main__':raise SystemExit(main())
