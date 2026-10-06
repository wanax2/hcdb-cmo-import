"""Automatic CMO -> HCDB weapon/sensor mapping for the foreign batch.
Writes auto_maps.json: {"W": {cmo_wid: spec}, "S": {cmo_sid: spec}, "log": [...]}
spec: int (existing HC id) | "SKIP" | "NAVDECOY" | ["DIV", hc, n] | ["NEWC", analog_hc, name, key, counterpart_cmo]
"""
import json, re, math, collections, os
import cmo_lib as L
import maps

L.HC = os.path.expanduser('~/w/base2')
D = L.load_cmo()
H = L.load_hc()
E = D['enum']
P = json.load(open('platforms5.json'))
used = json.load(open('used5.json'))

HCN = {}
for k in ['c1', 'd1', 'e1', 'f1', 'g1', 'g2', 'j1', 'm1']:
    for r in H[k][1]:
        HCN[int(r['id'])] = (k, r['classname'], r)

GEN = {'MOD', 'BLK', 'BLOCK', 'TYPE', 'CLASS', 'THE', 'AND', 'WITH', 'BURST', 'RNDS', 'HE', 'SALVO', 'MK', 'II', 'III', 'IV',
       'NUCLEAR', 'CONVENTIONAL', 'GUIDED', 'MISSILE', 'RADAR', 'SONAR', 'ACTIVE', 'PASSIVE', 'ARRAY', 'TOWED', 'HULL',
       'SEARCH', 'POD', 'GENERIC', 'VERSION', 'EXPORT', 'NAVAL', 'SHIP', 'AIR', 'LAUNCHED', 'ROUNDS', 'RND', 'LONG', 'RANGE'}


def desig(s):
    s = s.upper()
    out = set()
    for m in re.finditer(r'\b([A-Z]{1,5})[- .]?(\d+[A-Z0-9]*)(?:[- ](\d+[A-Z]*))?\b', s):
        out.add((m.group(1) + m.group(2) + (m.group(3) or '')).replace('.', ''))
        out.add(m.group(1) + m.group(2))
    for m in re.finditer(r'\b(\d+[A-Z]+\d+[A-Z0-9]*)\b', s):
        out.add(m.group(1))
    return {x for x in out if re.search(r'\d', x) and len(x) >= 3 and not re.fullmatch(r'(MK|MOD|BLK|NO|BATCH|V|T)\d', x)}


def words(s):
    return {w for w in re.findall(r'[A-Z]{4,}', s.upper()) if w not in GEN}


def caliber(s):
    m = re.search(r'(\d{2,3})\s?mm', s)
    return int(m.group(1)) if m else None


def inner(s):
    t = ' '.join(re.findall(r'[\[(]([^\])]*)[\])]', s))
    return desig(t)


def pmatch(x, y):
    return x == y or ((x.startswith(y) or y.startswith(x)) and re.fullmatch(r'[A-Z]*', (x[len(y):] if x.startswith(y) else y[len(x):])))


def score(a, b):
    if a.upper().startswith('CH-'):
        a = re.sub(r'^CH-\S+', '', a)
    da, db = desig(a), desig(b)
    ia, ib = inner(a), inner(b)
    sc = 0
    if ia and ib and not any(pmatch(x, y) for x in ia for y in ib):
        sc -= 6
    for x in da:
        for y in db:
            if x == y:
                sc += 4
            elif (x.startswith(y) or y.startswith(x)) and re.fullmatch(r'[A-Z]*', (x[len(y):] if x.startswith(y) else y[len(x):])):
                sc += 2
    sc += sum(2 if len(x) >= 7 else 1 for x in (words(a) & words(b)))
    ca, cb = caliber(a), caliber(b)
    if ca and cb and ca != cb:
        sc -= 10
    return sc


def best_match(name, annexes):
    best, bs = None, 0
    for i, (k, n, r) in HCN.items():
        if k not in annexes or 'zzdonotuse' in n:
            continue
        s = score(name, n)
        if s > bs or (s == bs and best and len(n) < len(HCN[best][1])):
            best, bs = i, s
    return best if bs >= 4 else None


def wstats(wid):
    w = D['Weapon'][wid]
    sp = []
    for p in D['WeaponPropulsion'].get(wid, []):
        sp += [int(x['Speed']) for x in D['PropulsionPerformance'].get(p['ComponentID'], [])]
    f = lambda x: float(x or 0)
    return dict(air=f(w['AirRangeMax']), surf=max(f(w['SurfaceRangeMax']), f(w['LandRangeMax'])), sub=f(w['SubsurfaceRangeMax']),
                speed=max(sp) if sp else 0, weight=f(w['Weight']), land=f(w['LandRangeMax']), shp=f(w['SurfaceRangeMax']))


def short(n, lim=27):
    n = re.sub(r'\s*\[(.*?)\]', r' (\1)', n).replace(',', ';').replace('"', '')
    n = re.sub(r'\s+', ' ', n).strip()
    return n if len(n) <= lim else n[:lim].rstrip(' (;')


# ---------- pairs known (CMO id -> HC id) for analog search
def weapon_domains():
    dom = collections.defaultdict(set)
    for fn in ('platforms.json', 'platforms5.json'):
        for p in json.load(open(fn)).values():
            k = 'air' if p['kind'] == 'air' else 'sea'
            for m in p['mounts']:
                for w in m['weapons']:
                    dom[w['wid']].add(k)
            for m in p['mags']:
                for w in m['weapons']:
                    dom[w['wid']].add(k)
            for l in p.get('loadouts', []):
                for w in l['weapons']:
                    dom[w['wid']].add('air')
    return dom


DOM = weapon_domains()


def role(wid):
    st = wstats(wid)
    d = 'air' if 'air' in DOM.get(wid, ()) else 'sea'
    if st['air'] and not st['surf']:
        return d + '-aa'
    if st['air'] and st['surf']:
        return d + '-aa'
    if st['surf']:
        guided_bomb = st['speed'] and st['speed'] < 650 and st['surf'] < 60 and d == 'air' and st['weight'] > 150
        return d + ('-bomb' if guided_bomb or not st['speed'] else '-ag')
    return d + '-other'


def known_pairs():
    pairs = {}
    for c, v in maps.W.items():
        if isinstance(v, int) and c in D['Weapon']:
            pairs[c] = v
    return pairs


WTYPE = lambda wid: E['EnumWeaponType'].get(D['Weapon'][wid]['Type'], '')
ANNEX_FOR = {'Guided Weapon': ('d1', 'e1'), 'Gun': ('c1',), 'Guided Projectile': ('c1', 'd1'), 'Torpedo': ('f1',),
             'Guided Depth Charge': ('e1', 'f1'), 'Depth Charge': ('e1',), 'Rocket': ('g1', 'd1'), 'Bomb': ('g1', 'd1'),
             'Decoy (Vehicle)': ('d1',)}


def nearest_analog(wid, annex, pairs):
    s = wstats(wid)
    best, bd = None, 1e9
    for c, h in pairs.items():
        if HCN.get(h, ('',))[0] != annex:
            continue
        t = wstats(c)
        if annex == 'd1' and role(c) != role(wid):
            continue
        if annex == 'c1' and ('air' in DOM.get(c, ())) != ('air' in DOM.get(wid, ())):
            continue
        if bool(s['air']) != bool(t['air']) or bool(s['surf']) != bool(t['surf']):
            pen = 3
        else:
            pen = 0
        d = pen + abs(math.log1p(s['air']) - math.log1p(t['air'])) + abs(math.log1p(s['surf']) - math.log1p(t['surf'])) \
            + 0.5 * abs(math.log1p(s['speed']) - math.log1p(t['speed'])) + 0.3 * abs(math.log1p(s['weight']) - math.log1p(t['weight']))
        if annex == 'c1':
            ca, cb = caliber(D['Weapon'][wid]['Name']), caliber(D['Weapon'][c]['Name'])
            d = abs((ca or 20) - (cb or 20)) / 10 + 0.2 * d
        if d < bd:
            best, bd = (h, c), d
    return best


def map_weapons():
    W, log = {}, []
    pairs = known_pairs()
    todo = [w for w in used['weapons'] if w not in maps.W]
    # pass 1: name matches
    rest = []
    for wid in todo:
        n = D['Weapon'][wid]['Name']
        t = WTYPE(wid)
        if t in ('Cargo', 'Paratroops', 'Aircraft', 'Training Round', 'Laser', 'Laser Dazzler', 'Decoy (Expendable)'):
            W[wid] = 'SKIP' if t != 'Decoy (Expendable)' else 'NAVDECOY'
            continue
        if t == 'Sonobuoy':
            W[wid] = 47367 if re.search(r'DICASS|active|CAMBS|RGB-2|RGB-16', n, re.I) else 47150
            continue
        if t in ('Drop Tank', 'Ferry Tank'):
            v = re.search(r'(\d+)\s*(USG|liter|l\b|L\b|kg)', n)
            lit = float(v.group(1)) * (3.785 if v and v.group(2) == 'USG' else 1) if v else 1000
            tanks = [(abs(math.log(lit) - math.log(float(re.match(r'(\d+)', HCN[i][1]).group(1)) * (3.785 if 'USG' in HCN[i][1] else 1))), i)
                     for i in HCN if HCN[i][0] == 'g1' and HCN[i][2].get('type') == '70' and re.match(r'\d+', HCN[i][1])]
            W[wid] = min(tanks)[1]
            continue
        if t in ('Bottom Mine', 'Moored Mine', 'Moving Mine', 'Rising Mine'):
            W[wid] = 26692 if wstats(wid)['weight'] > 400 else 26694
            continue
        if t == 'Decoy (Towed)':
            W[wid] = 'SKIP' if re.search(r'Nixie|Acoustic|Torpedo|SLQ|Sentor', n, re.I) else 34932
            continue
        if t == 'Sensor Pod':
            if re.search(r'ECM|jamm|DECM|SPS-|Sorbtsiya|Khibiny|Kh-?ibiny|Talisman|Elisra', n, re.I):
                W[wid] = 34818
            elif re.search(r'FLIR|target|Litening|Damocles|Talios|Sniper|LANTIRN|Pantera|Sapsan|Atlis', n, re.I):
                W[wid] = 34914
            else:
                W[wid] = 'SKIP'
            continue
        ann = ANNEX_FOR.get(t)
        if not ann:
            W[wid] = 'SKIP'
            continue
        m = best_match(n, ann)
        if m:
            W[wid] = m
            pairs.setdefault(wid, m)
            log.append(('weapon-match', n, HCN[m][1]))
        else:
            rest.append(wid)
    # pass 2: new items via analog
    newkeys = {}
    for wid in rest:
        n = D['Weapon'][wid]['Name']
        t = WTYPE(wid)
        st = wstats(wid)
        if t == 'Bomb' or (t == 'Rocket' and 'pod' not in n.lower()):
            if t == 'Rocket':
                W[wid] = ['DIV', 31054, 7]
                continue
            wt = st['weight']
            W[wid] = 30751 if re.search(r'RBK|cluster|CB\b|KMGU|BLU', n, re.I) else (31057 if wt < 200 else 30735 if wt < 350 else 30739 if wt < 700 else 30749)
            continue
        annex = {'Gun': 'c1', 'Guided Projectile': 'c1', 'Torpedo': 'f1', 'Guided Depth Charge': 'f1', 'Depth Charge': 'e1',
                 'Rocket': 'g1', 'Decoy (Vehicle)': 'd1'}.get(t, 'd1')
        if annex == 'd1' and st['sub'] and not st['air'] and not st['surf']:
            annex = 'e1'
        if annex == 'e1':
            W[wid] = 22591 if t == 'Depth Charge' else 22579
            continue
        if annex == 'g1':
            W[wid] = ['DIV', 31054, 7]
            continue
        if annex == 'c1' and re.search(r'Goalkeeper|CIWS|Gatling|Phalanx|H/PJ-1[14]|Type 730|Type 1130|AK-630|Kashtan|Palash|Millennium', n, re.I):
            an = (14462, '830')
        else:
            an = nearest_analog(wid, annex, pairs)
        if not an:
            W[wid] = 'SKIP'
            continue
        nm = short(n, {'c1': 26, 'd1': 27, 'f1': 19}[annex])
        key = 'auto_' + L.norm(nm)
        W[wid] = ['NEWC', an[0], nm, key, an[1]]
        log.append(('weapon-new', n, f'{nm} <- {HCN[an[0]][1]}'))
    return W, log


# ---------- sensors
SCATS = [
    ('aew', r'Air & Surface Search, 3D Long|Airborne Early|AEW', 43274, '2181'),
]


def sensor_kind_usage():
    k = collections.defaultdict(set)
    for p in P.values():
        for s in p['sensors']:
            k[s].add(p['kind'])
        for m in p['mounts']:
            for s in m['sensors']:
                k[s].add(p['kind'])
    return k


def map_sensors():
    S, log = {}, []
    usage = sensor_kind_usage()
    todo = [s for s in used['sensors'] if s not in maps.S]
    for sid in todo:
        s = D['Sensor'][sid]
        n = s['Name']
        typ = E['EnumSensorType'].get(s['Type'], '')
        role = E['EnumSensorRole'].get(s['Role'], '')
        rng = float(s['RangeMax'] or 0)
        kinds = usage.get(sid, set())
        if typ == 'Radar':
            if re.search(r'Tracker|Tracking|Illuminator|Gun Director|Fire Control|Front Dome|Front Door|Hot Shot|Eye Bowl|Bass Tilt|Power Shield|Type 34[357]|DRBC|Plank Shave', n) and not re.search(r'MFR|Poliment|SPY|APAR|EMPAR', n):
                continue
            if re.search(r'Weather|Air Traffic|Illuminator|Missile Approach|Counter-Battery|Navigation(?!.*Surface)|Terrain|Altimeter|Fuze', role) \
                    or (re.search(r'FCR, Surface-to-Air', role) and rng < 40 and 'ship' in kinds) or re.search(r'Fire Control|CIWS|Gun', role) or rng < 5:
                continue
            m = best_match(n, ('j1',))
            if m:
                S[sid] = m
                log.append(('radar-match', n, HCN[m][1]))
                continue
            if 'air' in kinds:
                if re.search(r'3D Long|Early Warning', role):
                    an, cp = 43274, '2181'
                elif re.search(r'Surface Search|Ground', role):
                    an, cp = 43506, '3768'
                else:
                    an, cp = 43318, '1379'
            elif 'sub' in kinds:
                an, cp = 43721, '660'
            else:
                if re.search(r'FCR|Multi|MFR', role) and rng >= 60:
                    an, cp = 43032, '1594'
                elif re.search(r'Air Search|3D|Air & Surface', role) and rng >= 60:
                    an, cp = 43576, '1645'
                elif re.search(r'Surface Search|Navigation', role):
                    S[sid] = 43176
                    continue
                else:
                    an, cp = 43556, '2314'
            nm = short(n, 27)
            S[sid] = ['NEWC', an, nm, 'auto_' + L.norm(nm), cp]
            log.append(('radar-new', n, f'{nm} <- {HCN[an][1]}'))
        elif 'Sonar' in typ or 'TASS' in typ or 'VDS' in typ:
            if (re.search(r'Active-Only', typ) and rng < 5) or re.search(r'Intercept|Warning|Acoustic Intercept', n + typ):
                continue
            m = best_match(n, ('m1',))
            if m:
                S[sid] = m
                log.append(('sonar-match', n, HCN[m][1]))
                continue
            if 'Dipping' in typ:
                an, cp = 47300, '625'
            elif 'VDS' in typ:
                an, cp = 47274, '4019'
            elif 'TASS' in typ:
                an, cp = (47379, '4808') if 'Active' in typ.split(',')[1] else (47119, '105')
            elif 'sub' in kinds:
                an, cp = (47114, '816') if 'Passive-Only' in typ else (47283, '2401')
            else:
                an, cp = (47256, '1381')
            nm = short(n, 29)
            S[sid] = ['NEWC', an, nm, 'auto_' + L.norm(nm), cp]
            log.append(('sonar-new', n, f'{nm} <- {HCN[an][1]}'))
    return S, log


if __name__ == '__main__':
    W, lw = map_weapons()
    S, ls = map_sensors()
    _byname = {}
    for i, v in HCN.items():
        _byname.setdefault(L.norm(v[1]), i)
    nfix = 0
    for M in (W, S):
        for k, v in list(M.items()):
            if isinstance(v, list) and v[0] == 'NEWC' and L.norm(v[2]) in _byname and HCN[_byname[L.norm(v[2])]][0] == HCN[v[1]][0]:
                M[k] = _byname[L.norm(v[2])]; nfix += 1
    print('NEWC name collisions -> existing', nfix)
    json.dump({'W': W, 'S': S, 'log': lw + ls}, open('auto_maps5.json', 'w'), indent=0)
    c = collections.Counter(('int' if isinstance(v, int) else v if isinstance(v, str) else v[0]) for v in W.values())
    print('weapons', c)
    c = collections.Counter(('int' if isinstance(v, int) else v if isinstance(v, str) else v[0]) for v in S.values())
    print('sensors', c)
