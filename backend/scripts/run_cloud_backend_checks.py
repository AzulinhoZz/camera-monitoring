"""Run the reviewed backend suite in its Linux/Python image without host app credentials."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True,help='already built local runtime image')
    parser.add_argument('--wheels',required=True,help='private directory prepared with --include-tests')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9._/-]*:[a-zA-Z0-9_.-]+',args.image):parser.error('explicit local repository:tag required')
    output=Path(args.output);wheels=Path(args.wheels)
    if not output.is_absolute() or output.is_symlink() or not wheels.is_absolute() or wheels.is_symlink():parser.error('absolute owned directories required')
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    for path in (output,wheels):
        if not path.is_dir() or path.stat().st_uid!=os.getuid() or path.stat().st_mode&0o077:parser.error('directories must be private and owned')
    root=Path(__file__).resolve().parents[2]
    runtime=json.loads(subprocess.check_output(['docker','image','inspect',args.image],text=True))[0]['Id']
    name='camera-cloud-qa-'+uuid4().hex[:10];qa_image=name+':test'
    try:
        with tempfile.TemporaryDirectory(prefix='camera-qa-source-',dir=output) as temporary:
            context=Path(temporary)
            # Copy only versioned/staged source. Never follow symlinks or copy .git, ignored .env or uploads.
            names=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
            for name_in_git in filter(None,names):
                relative=Path(name_in_git);source=root/relative
                if relative.is_absolute() or '..' in relative.parts or source.is_symlink():raise ValueError('unsafe tracked path')
                if source.is_file():
                    target=context/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            dockerfile=context/'Dockerfile.cloud-qa'
            dockerfile.write_text('FROM '+args.image+'\nUSER 0:0\nRUN --mount=type=bind,target=/src,readonly --mount=type=bind,from=wheels,target=/wheels,readonly pip install --no-index --find-links=/wheels --only-binary=:all: --require-hashes -r /src/backend/requirements-ci.lock && pip check\nCOPY --chown=65534:65534 . /repo\nWORKDIR /repo\nENV PYTHONDONTWRITEBYTECODE=1\nUSER 65534:65534\n')
            with (output/'build.log').open('w') as log:
                subprocess.run(['docker','buildx','build','--platform','linux/amd64','--network','none','--build-context','wheels='+str(wheels),'-f',str(dockerfile),'-t',qa_image,'--load',str(context)],check=True,stdout=log,stderr=log,timeout=300)
        marker='QA_JUNIT_'+uuid4().hex+'='
        test_command=['python','-m','pytest','-q','backend','--junitxml=/tmp/backend-tests.xml','-o','cache_dir=/tmp/pytest-cache']
        wrapper="import subprocess,pathlib,base64;result=subprocess.run("+repr(test_command)+");report=pathlib.Path('/tmp/backend-tests.xml');print("+repr(marker)+"+base64.b64encode(report.read_bytes()).decode(),flush=True);raise SystemExit(result.returncode)"
        subprocess.run(['docker','create','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','2g','--cpus','4','--tmpfs','/tmp:rw,mode=1777,noexec,nosuid,nodev','--tmpfs','/qa-tmp:rw,exec,mode=1777,nosuid,nodev','-e','TMPDIR=/qa-tmp','-e','SUPABASE_URL=','-e','SUPABASE_SECRET_KEY=','-e','FIREBASE_CREDENTIALS_PATH=','-e','GOOGLE_APPLICATION_CREDENTIALS=','-e','OMP_NUM_THREADS=1','-e','OPENBLAS_NUM_THREADS=1',qa_image,'python','-c',wrapper],check=True,capture_output=True)
        with (output/'tests.log').open('w') as log:subprocess.run(['docker','start','-a',name],stdout=log,stderr=log,timeout=300)
        state=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]['State']
        lines=(output/'tests.log').read_text().splitlines(True)
        encoded=next(line.strip()[len(marker):] for line in reversed(lines) if line.startswith(marker))
        (output/'backend-tests.xml').write_bytes(base64.b64decode(encoded,validate=True))
        (output/'tests.log').write_text(''.join(line for line in lines if not line.startswith(marker)))
        receipt={'exit_code':state['ExitCode'],'oom_killed':state['OOMKilled'],'runtime_image_id':runtime,'network':'none','read_only':True,'uid':'65534:65534','limits':'QA-only executable tmpfs permits the timeout fixture; production /tmp remains noexec. No managed integration.'}
        (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));return state['ExitCode']
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True)
        subprocess.run(['docker','image','rm',qa_image],capture_output=True)


if __name__=='__main__':raise SystemExit(main())
