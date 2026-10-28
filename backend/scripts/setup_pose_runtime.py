"""Explicit optional runtime setup; never called by API or camera startup."""
import argparse
from pathlib import Path
import platform
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    target=Path(args.output)
    if sys.version_info[:2]!=(3,12) or sys.platform!='linux' or platform.machine()!='x86_64':
        parser.error('audited runtime requires Python3.12 Linux x86_64')
    if not target.is_absolute() or target.resolve()==Path(sys.prefix).resolve():
        parser.error('choose a separate absolute runtime directory')
    if target.exists() and not (target/'pyvenv.cfg').is_file():
        parser.error('refusing to modify an existing non-venv directory')
    root=Path(__file__).resolve().parents[1]
    if not target.exists():subprocess.run([sys.executable,'-m','venv',str(target)],check=True)
    python=str(target/'bin/python')
    subprocess.run([python,'-m','pip','install','--no-cache-dir','--only-binary=:all:','--require-hashes','-r',str(root/'requirements-pose.lock')],check=True)
    subprocess.run([python,'-m','pip','check'],check=True)
    # Do not reuse a legacy or unrelated environment with unreviewed leftovers.
    import json,re
    allowed={re.split(r'==',line)[0].lower().replace('_','-') for line in (root/'requirements-pose.lock').read_text().splitlines() if line and not line.startswith('#')} | {'pip','setuptools','wheel'}
    installed=json.loads(subprocess.check_output([python,'-m','pip','list','--format=json'],text=True))
    if any(a['name'].lower().replace('_','-') not in allowed for a in installed):
        raise RuntimeError('unreviewed packages present; choose a fresh isolated directory')
    subprocess.run([python,str(root/'scripts/build_pose_tasks.py'),'--output',str(target/'share/camera-monitoring/models')],check=True)
    subprocess.run([python,'-c','from app.vision.pose_backend import verify_models; verify_models(); print("Audited bundled models verified")'],env=__import__('os').environ | {'PYTHONPATH':str(root)},check=True)

if __name__=='__main__':main()
