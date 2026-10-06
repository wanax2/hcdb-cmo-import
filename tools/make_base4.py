"""base4 = base2 (HCDB-250724 + US batch) minus the US batch's original loadout rows,
which build5 regenerates. Run after build5.py, before merge5.py."""
import json, shutil, os
W = os.path.expanduser('~/w')
us = set(json.load(open(f'{W}/built5.json'))['US_Y1'])
shutil.rmtree(f'{W}/base4', ignore_errors=True); shutil.copytree(f'{W}/base2', f'{W}/base4')
p = f'{W}/base4/annex_y1.csv'
lines = open(p, encoding='latin-1', newline='').read().split('\r\n')
keep = [lines[0]] + [l for l in lines[1:] if not l or int(l.split(',')[0]) not in us]
open(p, 'w', encoding='latin-1', newline='').write('\r\n'.join(keep))
print('removed', len(lines) - len(keep), 'US loadout rows')
