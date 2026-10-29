"""Create an artifact-hashed Maven/native APK inventory from Gradle's resolved graph.

No dependency resolution or execution here. Resolution is performed separately
by the existing reviewed Android toolchain. Missing POM licenses stay unknown.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--resolved',required=True);p.add_argument('--apk',required=True);p.add_argument('--pom-cache',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    rows=json.loads(Path(a.resolved).read_text());components={};contexts=defaultdict(set)
    for row in rows:
        purl=f'pkg:maven/{quote(row["group"],safe=".")}/{quote(row["name"],safe="")}@{quote(row["version"],safe="")}'
        reference=purl+'?artifact_sha256='+row['sha256']
        contexts[reference].add(row['configuration'])
        item={'type':'library','bom-ref':reference,'group':row['group'],'name':row['name'],'version':row['version'],'purl':purl,
              'hashes':[{'alg':'SHA-256','content':row['sha256']}],'properties':[{'name':'artifact:filename','value':row['filename']}]}
        licenses=[]
        for pom in (Path(a.pom_cache)/row['group']/row['name']/row['version']).glob('*/*.pom'):
            try:
                tree=ET.parse(pom)
                licenses += [node.text for node in tree.findall('.//{*}licenses/{*}license/{*}name') if node.text]
            except ET.ParseError:pass
        if licenses:item['licenses']=[{'license':{'name':name}} for name in sorted(set(licenses))]
        else:item['properties'].append({'name':'license-review','value':'POM metadata missing; manual review required'})
        components[reference]=item
    for reference,item in components.items():item['properties'].append({'name':'gradle:configurations','value':','.join(sorted(contexts[reference]))})
    apk=Path(a.apk);native=[]
    with zipfile.ZipFile(apk) as archive:
        for member in archive.infolist():
            if member.filename.startswith('lib/') and member.filename.endswith('.so'):
                if member.file_size>64*1024*1024:raise ValueError('native library budget')
                data=archive.read(member)
                native.append({'name':member.filename,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    for item in native:components[item['name']]={'type':'file','bom-ref':'apk:'+item['name'],'name':item['name'],'hashes':[{'alg':'SHA-256','content':item['sha256']}],'properties':[{'name':'version-review','value':'native version not inferred from filename'}]}
    output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
    (output/'android.cdx.json').write_text(json.dumps({'bomFormat':'CycloneDX','specVersion':'1.6','version':1,'components':list(components.values())},indent=2)+'\n')
    report={'resolved_artifact_rows':len(rows),'distinct_maven_artifacts':len(contexts),'configurations':sorted({r['configuration'] for r in rows}),
            'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'apk_bytes':apk.stat().st_size,'native_libraries':native,
            'scope':'resolved cached artifacts and debug APK only; no complete native/Maven vulnerability or legal audit, not a device test'}
    (output/'android-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('resolved_artifact_rows','distinct_maven_artifacts','configurations')}))

if __name__=='__main__':main()
