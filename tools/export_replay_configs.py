"""Export self-contained configs that do not depend on the original drive path."""
import argparse
import json
from pathlib import Path
import yaml


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root)
    count=0
    for path in sorted(root.glob('*/results.json')):
        j=json.loads(path.read_text(encoding='utf-8'));config=j['parameters'].copy()
        config.pop('inherit',None);config.pop('overrides',None)
        (path.parent/'resolved_config.yaml').write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False),encoding='utf-8')
        count+=1
    for path in sorted(root.glob('MC_*/summary.json')):
        j=json.loads(path.read_text(encoding='utf-8'));config=j['resolved_config'].copy()
        config.pop('inherit',None);config.pop('overrides',None);config['seed']=j['runs'][0]['seed']
        (path.parent/'first_realization_config.yaml').write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False),encoding='utf-8')
    print('PORTABLE REPLAY CONFIGS',count)


if __name__=='__main__':main()
