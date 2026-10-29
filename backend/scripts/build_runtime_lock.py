"""Derive runtime closure from installed, reviewed CI versions; never resolve latest."""
import argparse
import platform
import sys
import importlib.metadata as metadata
from pathlib import Path
from packaging.requirements import Requirement
from packaging.markers import default_environment
from packaging.utils import canonicalize_name


def runtime_names(roots):
    extras={};pending=[];seen={}
    def add(requirement):
        name=canonicalize_name(requirement.name)
        if not requirement.specifier.contains(metadata.version(name),prereleases=True):
            raise ValueError('installed distribution violates requirement')
        before=extras.get(name)
        merged=(before or set())|set(requirement.extras)
        if before is None or before!=merged:extras[name]=merged;pending.append(name)
    for root in roots:add(Requirement(root))
    while pending:
        name=pending.pop()
        contexts=extras[name]|{''}
        if seen.get(name)==contexts:continue
        seen[name]=contexts.copy()
        for text in metadata.requires(name) or []:
            req=Requirement(text)
            if req.marker is None or any(req.marker.evaluate(default_environment()|{'extra':extra}) for extra in contexts):add(req)
    return set(extras)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    if sys.version_info[:2]!=(3,12) or sys.platform!='linux' or platform.machine()!='x86_64':
        parser.error('runtime snapshot target is Python3.12 Linux x86_64')
    backend=Path(__file__).resolve().parents[1]
    roots=[s.strip() for s in (backend/'requirements.txt').read_text().splitlines() if s.strip() and not s.startswith('#')]
    names=runtime_names(roots)
    locked={canonicalize_name(line.split('==')[0]):line for line in (backend/'requirements-ci.lock').read_text().splitlines() if line and not line.startswith('#')}
    if names-locked.keys():raise ValueError('runtime dependency missing from reviewed hash lock')
    Path(args.output).write_text('# Runtime closure of reviewed CI snapshot; Python3.12 Linux x86_64 only.\n'+ '\n'.join(locked[n] for n in sorted(names))+'\n')
    print(f'{len(names)} reviewed runtime distributions; no test-only packages')

if __name__=='__main__':main()
