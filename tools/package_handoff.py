"""Package current files, including untracked implementation, without Git archive."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',default='results/release_20261113')
    parser.add_argument('--out',default='dist/programming_handoff_20261113.zip')
    parser.add_argument('--lite',action='store_true',help='Omit large field matrices; retain code, scalar results and MATLAB figures')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    result=(root/args.results).resolve()
    audit=json.loads((result/'audit.json').read_text(encoding='utf-8'))
    if audit['status']!='PASS':raise RuntimeError('Only package an audited result set')
    complete=json.loads((result/'completeness.json').read_text(encoding='utf-8'))
    if complete['status']!='PASS':raise RuntimeError('Release completeness checks must pass')
    figures=list((result/'figures').glob('*.png'))
    if len(figures)!=complete['MATLAB_png']:raise RuntimeError('Figure manifest mismatch')
    paths=set()
    for dirname in ('src','tests','configs','matlab','modeling','handoff','tools','data/raw','problem','meta','ledger'):
        for p in (root/dirname).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':paths.add(p)
    for p in root.glob('*.md'):paths.add(p)
    for name in ('requirements.txt','CODE_VERSION.json','.gitattributes','.gitignore'):
        if (root/name).exists():paths.add(root/name)
    for p in (root/'资料').rglob('*.md'):paths.add(p)
    for p in result.rglob('*'):
        if p.is_file():
            if args.lite and p.name in ('fields.npz','fields.mat','manifest.json'):continue
            paths.add(p)
    for logfile in result.parent.glob(result.name+'*.log'):
        if logfile.is_file():paths.add(logfile)
    out=(root/args.out).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(paths):archive.write(p,p.relative_to(root).as_posix())
        archive.writestr('PACKAGE_MANIFEST.json',json.dumps(manifest,indent=2,ensure_ascii=False))
        if args.lite:
            archive.writestr('LIGHTWEIGHT_README.md',
                '# Lightweight review package\n\nAll source, parameter inputs, scalar results, ledgers, events and MATLAB PNG/PDF pairs are included. '
                'The large fields.npz/fields.mat matrices and the full result manifest are omitted. '
                'PACKAGE_MANIFEST.json lists the actual included files. Use the full package for stored spatiotemporal fields, '
                'or rerun the documented deterministic batch to regenerate matrices before rerunning MATLAB.\n')
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.sha256').write_text(digest+'  '+out.name+'\n',encoding='utf-8')
    print(out, f'{out.stat().st_size/1e6:.1f} MB',len(paths),'files',digest)


if __name__=='__main__':main()
