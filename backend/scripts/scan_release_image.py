"""Review-pinned external scanners. A missing vulnerability DB is BLOCKED, never PASS."""
import argparse
from datetime import datetime, timezone, timedelta
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


def archive_identity(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    with tarfile.open(path) as bundle:
        members=bundle.getmembers()
        if len({m.name for m in members})!=len(members):raise ValueError('duplicate archive paths')
        def read(name):
            member=bundle.getmember(name)
            if not member.isfile() or member.size>2*1024*1024:raise ValueError('invalid image metadata')
            return bundle.extractfile(member).read()
        manifest=json.loads(read('manifest.json'))
        if not isinstance(manifest,list) or len(manifest)!=1:raise ValueError('single image archive required')
        config=manifest[0]['Config']
        if not re.fullmatch(r'(?:blobs/sha256/)?[a-f0-9]{64}(?:\.json)?',config):raise ValueError('invalid config path')
        config_digest=hashlib.sha256(read(config)).hexdigest()
        if Path(config).name.removesuffix('.json')!=config_digest:raise ValueError('config digest mismatch')
    return {'image_id':'sha256:'+config_digest,'archive_sha256':digest.hexdigest()}


def scanner_environment(cache):
    # Supply transport/TLS configuration, never application credentials or
    # ambient scanner overrides that could suppress findings.
    allowed={'PATH','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy',
             'all_proxy','no_proxy','SSL_CERT_FILE','SSL_CERT_DIR','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','LANG','LC_ALL','TZ'}
    env={key:value for key,value in os.environ.items() if key in allowed}
    home=cache/'home';home.mkdir(mode=0o700,exist_ok=True)
    env.update(HOME=str(home),XDG_CACHE_HOME=str(cache/'xdg'),
               SYFT_CHECK_FOR_APP_UPDATE='false',GRYPE_CHECK_FOR_APP_UPDATE='false')
    return env


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


def verified_match_count(findings, now=None):
    """A successful process exit alone does not establish database validity."""
    matches=findings.get('matches')
    status=findings.get('descriptor',{}).get('db',{}).get('status',{})
    if not isinstance(matches,list) or status.get('valid') is not True or status.get('error'):
        raise ValueError('incomplete scanner result or invalid database')
    built=datetime.fromisoformat(status['built'].replace('Z','+00:00'))
    if built.tzinfo is None:raise ValueError('database timestamp lacks timezone')
    age=(now or datetime.now(timezone.utc))-built
    if age>timedelta(hours=72) or age < -timedelta(hours=1):
        raise ValueError('database age outside allowed window')
    return len(matches)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',required=True);p.add_argument('--output',required=True);p.add_argument('--cache',required=True);p.add_argument('--db-archive');p.add_argument('--db-sha256');a=p.parse_args()
    if bool(a.db_archive)!=bool(a.db_sha256):p.error('--db-archive and official --db-sha256 are required together')
    if platform.system()!='Linux' or platform.machine()!='x86_64':p.error('reviewed scanners target Linux x86_64')
    output=Path(a.output);output.mkdir(parents=True,mode=0o700,exist_ok=True)
    cache=Path(a.cache);cache.mkdir(parents=True,mode=0o700,exist_ok=True)
    if cache.is_symlink() or cache.stat().st_uid!=os.getuid() or cache.stat().st_mode&0o077:p.error('scanner cache must be private and owned by this UID')
    archive=Path(a.archive).resolve(strict=True)
    records=json.loads((Path(__file__).resolve().parents[2]/'docs/ai-vision/PHASE_6_SCANNER_REVIEW.json').read_text())
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'inventory':'NOT_RUN','vulnerability_scan':'BLOCKED','accepted':False,'limits':'Unsigned local receipt; full archive hash and config identity bind the input, not approval. Failures and findings never become clean acceptance.'}
    env=scanner_environment(cache)
    # Explicit configs prevent a checkout .grype.yaml or inherited GRYPE_*
    # variables from silently excluding vulnerable packages.
    grype_config=output/'grype-config.json'
    grype_config.write_text(json.dumps({'check-for-app-update':False,'only-fixed':False,'only-notfixed':False,
        'ignore-wontfix':'','ignore':[],'exclude':[],
        'db':{'cache-dir':str(cache/'grype-db'),'auto-update':not bool(a.db_archive),
              'validate-age':True,'max-allowed-built-age':'72h','validate-by-hash-on-start':True}}))
    syft_config=output/'syft-config.json';syft_config.write_text(json.dumps({'check-for-app-update':False}))
    try:
        report.update(archive_identity(archive))
        executables={r['tool']:acquire(r,cache) for r in records}
        with (output/'syft.log').open('w') as log:
            subprocess.run([str(executables['syft']),'-c',str(syft_config),'docker-archive:'+str(archive),'-o','cyclonedx-json='+str(output/'image.cdx.json')],env=env,stdout=log,stderr=log,timeout=180,check=True)
        report['inventory']='PASS'
        if a.db_archive:
            database=verify_database_archive(a.db_archive,a.db_sha256)
            with (output/'db-import.log').open('w') as log:
                subprocess.run([str(executables['grype']),'-c',str(grype_config),'db','import',str(database)],env=env,stdout=log,stderr=log,timeout=180,check=True)
            report['database_source']={'mode':'offline','sha256':a.db_sha256,'limits':'Integrity verified; official origin requires trusted out-of-band metadata.'}
        with (output/'grype.log').open('w') as log:
            result=subprocess.run([str(executables['grype']),'-c',str(grype_config),'sbom:'+str(output/'image.cdx.json'),'-o','json','--file',str(output/'vulnerabilities.json')],env=env,stdout=log,stderr=log,timeout=180)
        if result.returncode==0:
            findings=json.loads((output/'vulnerabilities.json').read_text())
            count=verified_match_count(findings);report.update(vulnerability_scan='PASS' if count==0 else 'FINDINGS',findings=count,accepted=count==0)
            report['database']=findings['descriptor']['db']['status']
        else:report['reason']='Grype failed; inspect log and provide an accessible, fresh official DB. No clean result.'
    except Exception as exc:
        report['reason']=type(exc).__name__+': scanner execution incomplete'
    (output/'scan-status.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['accepted'] else 1

if __name__=='__main__':raise SystemExit(main())
