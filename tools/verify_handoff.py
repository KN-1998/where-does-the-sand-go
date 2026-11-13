"""Verify transport SHA-256 and every archived payload against its manifest."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def archived_source_sha256(archive):
    digest = hashlib.sha256()
    paths = sorted(Path(name) for name in archive.namelist()
                   if name.startswith('src/') and name.endswith('.py'))
    if not paths:
        raise RuntimeError('Missing archived Python source')
    for path in paths:
        digest.update(path.relative_to('src').as_posix().encode('utf-8'))
        digest.update(b'\0')
        digest.update(archive.read(path.as_posix()))
        digest.update(b'\0')
    return digest.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('archives',nargs='+');p.add_argument('--out',required=True);a=p.parse_args()
    records=[]
    for name in a.archives:
        path=Path(name);digest=hashlib.sha256(path.read_bytes()).hexdigest()
        expected=path.with_suffix('.sha256').read_text(encoding='utf-8').split()[0]
        if digest!=expected:raise RuntimeError(f'Archive SHA-256 mismatch: {path}')
        with ZipFile(path) as z:
            names=z.namelist()
            if len(names)!=len(set(names)):raise RuntimeError('Duplicate archive members')
            manifest=json.loads(z.read('PACKAGE_MANIFEST.json'))
            if set(names)-set(manifest)-{'PACKAGE_MANIFEST.json','LIGHTWEIGHT_README.md'}:
                raise RuntimeError('Unmanifested payload')
            for member,sha in manifest.items():
                if hashlib.sha256(z.read(member)).hexdigest()!=sha:
                    raise RuntimeError(f'Payload SHA-256 mismatch: {member}')
            code=json.loads(z.read('CODE_VERSION.json'))
            if archived_source_sha256(z)!=code['src_sha256']:
                raise RuntimeError('Archived source bytes do not match the recorded source version')
            results=[n for n in names if n.endswith('/completeness.json')]
            if len(results)!=1:raise RuntimeError('Ambiguous release metadata')
            complete=json.loads(z.read(results[0]))
            if code['src_sha256']!=complete['code_sha256'] or complete['status']!='PASS':
                raise RuntimeError('Source/release identity mismatch')
            records.append({'archive':path.name,'status':'PASS','sha256':digest,
                'bytes':path.stat().st_size,'verified_payloads':len(manifest),
                'src_sha256':code['src_sha256'],'archived_source_rehashed':True})
    Path(a.out).write_text(json.dumps({'status':'PASS','archives':records},indent=2),encoding='utf-8')
    print(json.dumps(records,indent=2))


if __name__=='__main__':main()
