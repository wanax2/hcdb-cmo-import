"""Loader for the CMO DB3K CSV export + HCDB CSVs."""
import csv, os, pickle, collections, re

CMO = os.path.expanduser('~/w/cmo')
HC = os.path.expanduser('~/w/hc/res')


def _rd(path):
    with open(path, encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def _junction(name):
    d = collections.defaultdict(list)
    for r in _rd(f'{CMO}/3_Junction_Tables/DB3K_{name}.csv'):
        d[r['ID']].append(r)
    for k in d:
        if 'ComponentNumber' in d[k][0]:
            d[k].sort(key=lambda r: int(r['ComponentNumber']))
    return dict(d)


def _core(name):
    return {r['ID']: r for r in _rd(f'{CMO}/2_Core_Entities/DB3K_{name}.csv')}


def _enum(name):
    return {r['ID']: r['Description'] for r in _rd(f'{CMO}/1_Lookup_Tables/Enum_{name}.csv')}


def load_cmo():
    cache = os.path.expanduser('~/w/cmo.pkl')
    if os.path.exists(cache):
        return pickle.load(open(cache, 'rb'))
    D = {}
    for c in ['Ship', 'Submarine', 'Aircraft', 'Weapon', 'Sensor', 'Mount', 'Magazine',
              'Propulsion', 'Warhead', 'Loadout', 'Facility', 'Comm']:
        D[c] = _core('Data' + c)
    for j in ['ShipMounts', 'ShipSensors', 'ShipMagazines', 'ShipPropulsion', 'ShipCodes',
              'ShipAircraftFacilities', 'ShipSignatures',
              'SubmarineMounts', 'SubmarineSensors', 'SubmarineMagazines', 'SubmarinePropulsion',
              'SubmarineCodes', 'SubmarineSignatures',
              'AircraftMounts', 'AircraftSensors', 'AircraftLoadouts', 'AircraftPropulsion',
              'AircraftCodes', 'AircraftSignatures', 'AircraftFuel',
              'MountWeapons', 'MountSensors', 'MountMagazineWeapons', 'MagazineWeapons',
              'LoadoutWeapons', 'WeaponWarheads', 'WeaponTargets', 'WeaponSensors',
              'WeaponCodes', 'WeaponPropulsion', 'SensorCapabilities', 'SensorCodes',
              'PropulsionPerformance', 'ShipFuel', 'SubmarineFuel', 'WeaponFuel']:
        p = f'{CMO}/3_Junction_Tables/DB3K_Data{j}.csv'
        if os.path.exists(p):
            D[j] = _junction('Data' + j)
    D['WeaponRecord'] = {r['ID']: r for r in _rd(f'{CMO}/3_Junction_Tables/DB3K_DataWeaponRecord.csv')}
    D['enum'] = {}
    for f in os.listdir(f'{CMO}/1_Lookup_Tables'):
        D['enum'][f[5:-4]] = _enum(f[5:-4])
    # flat decoded tables
    D['flat'] = {k: {r['ID']: r for r in _rd(f'{CMO}/DB3K_{k}.csv')}
                 for k in ['Ships', 'Submarines', 'Aircraft', 'Weapons', 'Sensors']}
    pickle.dump(D, open(cache, 'wb'))
    return D


def load_hc():
    H = {}
    for f in sorted(os.listdir(HC)):
        if not f.endswith('.csv') or 'bs_strings' in f:
            continue
        with open(f'{HC}/{f}', encoding='latin-1', newline='') as fh:
            r = csv.reader(fh, skipinitialspace=True)
            hdr = [x.strip() for x in next(r)]
            rows = [dict(zip(hdr, row)) for row in r if row]
        H[f[6:-4]] = (hdr, rows)
    bs = {}
    for line in open(f'{HC}/annex_bs_strings.csv', encoding='latin-1'):
        if line.startswith('"'):
            p = next(csv.reader([line]))
            bs[p[0]] = p[3:]
    H['bs'] = bs
    return H


def arr(s):
    p = [int(x) for x in str(s).split(':')]
    return p[1:1 + p[0]] if p and p[0] > 0 else []


def mkarr(vals):
    vals = list(vals)
    return ':'.join(str(v) for v in [len(vals)] + vals)


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())
