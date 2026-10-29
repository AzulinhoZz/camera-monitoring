"""Fail closed on unresolved acceptance gates. Does not deploy, publish or approve."""
import argparse
import json
import re
from pathlib import Path

REQUIRED={'regression','database_restore','image_build_smoke','image_vulnerability_scan',
          'python_advisories','android_device','managed_staging','target_load_and_accuracy',
          'backup_operations','remote_ci','licenses','operator_approval'}


def verdict(document):
    gates=document.get('gates',{})
    unresolved=sorted(REQUIRED-set(gates))
    unresolved+=sorted(name for name in REQUIRED & set(gates) if gates[name].get('status')!='PASS' or not gates[name].get('evidence'))
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',str(document.get('image_id',''))) or not re.fullmatch(r'[a-f0-9]{64}',str(document.get('archive_sha256',''))):unresolved.append('candidate_identity')
    return {'decision':'NO_GO' if unresolved else 'GO_FOR_REVIEW',
            'unresolved':unresolved,'deploy_authorized':False,
            'limits':'A locally edited manifest is not an approval or signature. No deployment is performed.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',required=True);args=parser.parse_args()
    try:
        path=Path(args.manifest)
        if path.stat().st_size>1024*1024:raise ValueError('manifest size')
        result=verdict(json.loads(path.read_text()))
    except Exception:
        result={'decision':'NO_GO','unresolved':['invalid_manifest'],'deploy_authorized':False}
    print(json.dumps(result))
    return 0 if result['decision']=='GO_FOR_REVIEW' else 1

if __name__=='__main__':raise SystemExit(main())
