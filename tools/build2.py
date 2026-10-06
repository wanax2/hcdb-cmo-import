"""Build HCDB rows for selected CMO platforms."""
import cmo_lib as L, maps, json, re, collections, math, copy, os
L.HC = os.path.expanduser('~/w/base2')
AUTO = json.load(open('auto_maps.json'))
AUTO_W, AUTO_S = AUTO['W'], AUTO['S']

D = L.load_cmo()
H = L.load_hc()
E = D['enum']
P = json.load(open('platforms2.json'))
BS = H['bs']
LOG = []          # review log rows

# ------------------------------------------------------------------ HC indexes
HROW = {}
for k, v in H.items():
    if k == 'bs':
        continue
    hdr, rows = v
    for r in rows:
        HROW[(k, int(r[hdr[0]]))] = r
HC_BY_ID = {}
for k in ['a1', 'a2', 'b1', 'c1', 'd1', 'e1', 'f1', 'g1', 'g2', 'i1', 'j1', 'm1', 'p1', 'y1', 'z1', 'z2']:
    for r in H[k][1]:
        HC_BY_ID[int(r['id'])] = (k, r)
HC_BY_NAME = {}
for k in ['a1', 'a2', 'b1']:
    for r in H[k][1]:
        HC_BY_NAME[(k, r['classname'])] = r
MAGS = {int(r['index']): r for r in H['mags'][1]}
SHIPNAMES = {int(r['ship_id']): r for r in H['ship_names'][1]}
USA = BS['CountryName'].index('USA')

NEW = collections.OrderedDict()   # annex -> list of row dicts (in order)
for k in ['a1', 'a2', 'b1', 'c1', 'd1', 'e1', 'f1', 'g1', 'g2', 'j1', 'm1', 'y1', 'z1', 'z2']:
    NEW[k] = []
NEW_MAGS, NEW_NAMES, NEW_STR = [], [], []


class Alloc:
    def __init__(self):
        self.next = {}

    def get(self, annex):
        if annex not in self.next:
            ids = [int(r['id']) for r in H[annex][1]]
            base = min(ids) // 4096 * 4096
            low = [i for i in ids if i < base + 2048]
            self.next[annex] = (max(low) + 1) if low else base
        v = self.next[annex]
        self.next[annex] += 1
        return v


A = Alloc()
next_mag = max(MAGS) + 1
next_name = max(int(r['index']) for r in H['ship_names'][1]) + 1
next_str = max(int(r['index']) for r in H['strings'][1]) + 1


def add_string(text):
    global next_str
    text = text.replace('"', "'").replace('\n', ' ').strip()
    if len(text) > 800:
        text = text[:797].rsplit(' ', 1)[0] + '...'
    i = next_str
    next_str += 1
    NEW_STR.append((i, text))
    return i


def add_mag(wid, count, reload_t=5):
    global next_mag
    i = next_mag
    next_mag += 1
    NEW_MAGS.append((i, wid, min(int(count), 255), reload_t))
    return i


def add_names(ship_id, names):
    global next_name
    names = [n.replace('"', "'") for n in names][:40]
    if not names:
        return
    NEW_NAMES.append((next_name, ship_id, names))
    next_name += 1


def fnum(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


# ------------------------------------------------------------------ CMO helpers
def cmo_weapon_stats(wid):
    w = D['Weapon'][wid]
    sp = []
    for p in D['WeaponPropulsion'].get(wid, []):
        sp += [int(x['Speed']) for x in D['PropulsionPerformance'].get(p['ComponentID'], [])]
    wh = [D['Warhead'][x['ComponentID']] for x in D['WeaponWarheads'].get(wid, []) if x['ComponentID'] in D['Warhead']]
    return {
        'air': fnum(w['AirRangeMax']), 'surf': max(fnum(w['SurfaceRangeMax']), fnum(w['LandRangeMax'])),
        'sub': fnum(w['SubsurfaceRangeMax']),
        'pok_air': fnum(w['AirPoK']), 'pok_surf': max(fnum(w['SurfacePoK']), fnum(w['LandPoK'])),
        'speed': max(sp) if sp else 0,
        'wh': sum(fnum(h['ExplosivesWeight']) * max(1, int(fnum(h['NumberOfWarheads'], 1))) for h in wh),
    }


def cmo_counterpart(hc_id):
    """a CMO weapon id that maps to this existing HC id (for ratio scaling)"""
    for c, v in maps.W.items():
        if v == hc_id:
            return c
    return None


def scale(val, new, old, lo=None):
    val = float(val)
    if old and new:
        return int(round(val * new / old))
    return int(round(val))


# ------------------------------------------------------------------ weapons
NEWW = {}   # key -> hc id
CP_OVR = {}
WEAP_OVR = {'sm3_2a': {'airrange': '3000'}, 'sm2_3c': {'surfrange': '400'}, 'lrasm': {'dp': '90'},
            'arrw': {'dp': '50'}}
SENS_OVR = {'sabr': {'maxrange': '1700'}}


def make_new_weapon(spec, cmo_wid):
    _, analog, name, key = spec
    if key in NEWW:
        return NEWW[key]
    annex, arow = HC_BY_ID[analog]
    row = dict(arow)
    cp = CP_OVR.get(key) or cmo_counterpart(analog)
    new = cmo_weapon_stats(cmo_wid)
    old = cmo_weapon_stats(cp) if cp else None
    notes = [f'cloned from {arow["classname"]} ({analog})']
    if annex == 'd1' and old:
        if int(row['surfrange']) and not new['surf'] and not new['sub']:
            row['surfrange'] = '0'
        elif int(row['surfrange']):
            row['surfrange'] = str(scale(row['surfrange'], new['surf'], old['surf']))
        elif new['surf'] and not old['surf']:
            row['surfrange'] = str(int(new['surf'] * 10))
        if int(row['airrange']) and not new['air']:
            row['airrange'] = '0'
            row['airph'] = '0'
        elif int(row['airrange']):
            row['airrange'] = str(scale(row['airrange'], new['air'], old['air']))
        elif new['air'] and not old['air']:
            row['airrange'] = str(int(new['air'] * 8))
        if new['speed'] and old['speed']:
            row['speed'] = str(scale(row['speed'], new['speed'], old['speed']))
        if int(row['dp']) < 38912 and new['wh'] and old['wh']:
            row['dp'] = str(max(1, scale(row['dp'], new['wh'] ** 0.5, old['wh'] ** 0.5)))
        for f, pk in (('surfph', 'pok_surf'), ('airph', 'pok_air')):
            if int(row[f]) and new[pk] and old[pk]:
                row[f] = str(max(5, min(99, int(row[f]) + int(new[pk] - old[pk]))))
    if annex == 'c1' and old:
        for f, k2 in (('surfrange', 'surf'), ('airrange', 'air')):
            if int(row[f]) and new[k2] and old[k2]:
                row[f] = str(max(1, min(int(int(row[f]) * 2), scale(row[f], new[k2], old[k2]))))
        if new['wh'] and old['wh'] and int(row['dp']):
            row['dp'] = str(max(1, scale(row['dp'], new['wh'] ** 0.5, old['wh'] ** 0.5)))
    # hand adjustments
    ADJ = {
        'lrasm': lambda: dict(missleflags=str(int(row['missleflags']) | 1 << 5 | 1 << 4), guidance=str(int(row['guidance']) | 1 << 4 | 1 << 1), surfph='90'),
        'tlam_mst': lambda: dict(missleflags=str(int(row['missleflags']) | 1 << 5), guidance=str(int(row['guidance']) | 1 << 1 | 1 << 5 | 1 << 6), surfph='90'),
        'hpn2p': lambda: dict(missleflags=str(int(row['missleflags']) | 1 << 4), guidance=str(int(row['guidance']) | 1 << 6)),
        'essm2': lambda: dict(airph=str(min(99, int(row['airph']) + 5)), guidance=str(int(row['guidance']) | 1 << 5)),
        'jagm': lambda: dict(surfph=str(min(99, int(row['surfph']) + 5)), guidance=str(int(row['guidance']) | 1 << 5)),
        'sm2_3c': lambda: dict(guidance=str(int(row['guidance']) | 1 << 5), surfrange=str(max(int(row['surfrange']), int(row['airrange']) // 2))),
        'lrso': lambda: dict(dp='38923', surfph='95'),
        'arrw': lambda: dict(surfph='85'),
        'aim174': lambda: dict(airph=str(int(row['airph']))),
        'ngj': lambda: dict(modifier=str(min(99, int(row.get('modifier', 50)) + 15))),
    }
    adj = ADJ[key]() if key in ADJ else {}
    row.update(adj)
    row.update(WEAP_OVR.get(key, {}))
    row['id'] = str(A.get(annex))
    row['classname'] = name
    NEW[annex].append(row)
    NEWW[key] = int(row['id'])
    LOG.append(('weapon', name, annex, row['id'], '; '.join(notes), D['Weapon'][cmo_wid]['Name']))
    return int(row['id'])


def hc_weapon(cmo_wid, qty=1):
    """-> (hc_id, qty) or None"""
    v = maps.W.get(str(cmo_wid), AUTO_W.get(str(cmo_wid)))
    if isinstance(v, list):
        v = tuple(v)
    if v is None or v in ('SKIP', 'NAVDECOY'):
        return None
    if isinstance(v, int):
        return v, qty
    if v[0] == 'DIV':
        return v[1], max(1, math.ceil(qty / v[2]))
    if v[0] == 'NEWC':
        CP_OVR[v[3]] = v[4]
        return make_new_weapon(('NEW', v[1], v[2], v[3]), str(cmo_wid)), qty
    return make_new_weapon(v, str(cmo_wid)), qty


# ------------------------------------------------------------------ sensors
NEWS = {}


def cmo_sensor_range(sid):
    return fnum(D['Sensor'][sid]['RangeMax'])


def hc_sensor(cmo_sid):
    v = maps.S.get(str(cmo_sid), AUTO_S.get(str(cmo_sid)))
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if v[0] == 'NEWC':
        _, analog, name, key, cpo = v
    else:
        _, analog, name, key = v
        cpo = None
    if key in NEWS:
        return NEWS[key]
    annex, arow = HC_BY_ID[analog]
    row = dict(arow)
    cp = cpo or next((c for c, x in maps.S.items() if x == analog), None)
    if cp and annex == 'j1':
        r_new, r_old = cmo_sensor_range(str(cmo_sid)), cmo_sensor_range(cp)
        row['maxrange'] = str(max(20, min(int(int(row['maxrange']) * 1.6), scale(row['maxrange'], r_new, r_old))))
    if cp and annex == 'm1':
        r_new, r_old = cmo_sensor_range(str(cmo_sid)), cmo_sensor_range(cp)
        for f in ('activerange', 'passiverange'):
            if int(row[f]) and r_new and r_old:
                row[f] = str(max(1, min(int(int(row[f]) * 1.5), scale(row[f], r_new, r_old))))
    row.update(SENS_OVR.get(key, {}))
    row['id'] = str(A.get(annex))
    row['classname'] = name
    NEW[annex].append(row)
    NEWS[key] = int(row['id'])
    LOG.append(('sensor', name, annex, row['id'], f'cloned from {arow["classname"]} ({analog})', D['Sensor'][str(cmo_sid)]['Name']))
    return int(row['id'])


# ------------------------------------------------------------------ arcs
CMO_SEG = {  # CMO segment -> (start,end) degrees
    'SB1': (0, 22.5), 'SB2': (22.5, 45), 'SMF1': (45, 67.5), 'SMF2': (67.5, 90),
    'SMA1': (90, 112.5), 'SMA2': (112.5, 135), 'SS1': (135, 157.5), 'SS2': (157.5, 180),
    'PS2': (180, 202.5), 'PS1': (202.5, 225), 'PMA2': (225, 247.5), 'PMA1': (247.5, 270),
    'PMF2': (270, 292.5), 'PMF1': (292.5, 315), 'PB2': (315, 337.5), 'PB1': (337.5, 360)}


def hc_arc(segs):
    mask = 0
    for i in range(12):
        c = i * 30 + 15
        for s in segs:
            a, b = CMO_SEG[s]
            if a <= c < b:
                mask |= 1 << i
    if not segs:
        mask = 4095
    return mask


# ------------------------------------------------------------------ mounts
def classify(hc_id):
    annex = HC_BY_ID[hc_id][0] if hc_id in HC_BY_ID else None
    for k, rows in NEW.items():
        if any(int(r['id']) == hc_id for r in rows):
            annex = k
    return annex


def weapon_name(hc_id):
    if hc_id in HC_BY_ID:
        return HC_BY_ID[hc_id][1].get('classname', '')
    for rows in NEW.values():
        for r in rows:
            if int(r['id']) == hc_id:
                return r.get('classname', '')
    return '?'


def cavity_for(hc_id, mname):
    a = classify(hc_id)
    n = mname.lower()
    if 'vls' in n or 'mk41' in n or 'mk57' in n or 'cell' in n:
        return 4
    if a == 'c1':
        return 5 if ('ciws' in weapon_name(hc_id).lower() or 'phalanx' in n) else 2
    if a == 'f1' or 'tube' in n or 'tt' in n.split():
        return 0
    if a == 'd1':
        return 1 if ('rail' in n or 'ram' in n or 'mk49' in n) else 4
    return 0


MG = {14399, 14446}
ZCACHE = {}
PENDING = []
FAMILY = [r'SM-2', r'SM-3', r'SM-6', r'TLAM|TACTOM|Tomahawk', r'ESSM', r'Harpoon', r'Mk4[68]|Mk5[04]', r'RAM']


def consolidate(recs):
    """merge weapons of the same family into the most plentiful member"""
    out = collections.OrderedDict()
    fam_of = {}
    for i, q in recs:
        nm = weapon_name(i)
        fam = next((f for f in FAMILY if re.search(f, nm)), nm)
        fam_of.setdefault(fam, []).append((i, q))
    for fam, lst in fam_of.items():
        best = max(lst, key=lambda x: (x[1], x[0]))[0]
        out[best] = sum(q for _, q in lst)
    return list(out.items())


def mount_defaults(wep):
    """most common z1 settings used in HCDB for this weapon (or z2 group containing it)"""
    rows = [r for r in H['z1'][1] if int(r['wepid']) == wep]
    if not rows:
        grp = {int(z['id']) for z in H['z2'][1] if wep in L.arr(z['weapon_array'])}
        rows = [r for r in H['z1'][1] if int(r['wepid']) in grp]
    if not rows:
        return None
    pick = collections.Counter((r['numtargets'], r['ratoffire'], r['autonomous'], r['cavitylabel'], r['mntarmor']) for r in rows).most_common(1)[0][0]
    return dict(zip(('numtargets', 'ratoffire', 'autonomous', 'cavitylabel', 'mntarmor'), pick))


def base_weapon(hc):
    """for NEW weapons, the analog id"""
    for v in maps.W.values():
        if isinstance(v, tuple) and v[0] == 'NEW' and NEWW.get(v[3]) == hc:
            return v[1]
    return hc


def build_mounts(Pl, analog, kind, big=True):
    """returns list of z1 ids"""
    out = []
    used_hc = set()
    # keep analog's non-weapon structural mounts (helo pads, catapults, elevators) and decoy/ECM suites
    struct = []
    for mid in L.arr(analog['mount_array']):
        z = HROW[('z1', mid)]
        w = int(z['wepid'])
        if w == 65535 and z['cavitylabel'] == '255':
            struct.append(mid)
        elif w in (34946, 34947, 34948, 34949, 34950, 34951, 34940, 34941, 34942, 34943, 34944, 34945):
            struct.append(mid)
    navdecoy = False
    PENDING.clear()
    work = list(Pl['mounts'])
    i_w = 0
    while i_w < len(work) or PENDING:
        if PENDING:
            m = PENDING.pop(0)
        else:
            m = work[i_w]
            i_w += 1
        recs = list(m.get('_recs', []))
        for w in m['weapons']:
            if maps.W.get(str(w['wid'])) == 'NAVDECOY':
                navdecoy = True
                continue
            if not w['load']:
                continue
            r = hc_weapon(w['wid'], w['load'])
            if r:
                recs.append((r[0], r[1]))
        if not recs:
            continue
        # merge dup ids
        agg = collections.OrderedDict()
        for i, q in recs:
            agg[i] = agg.get(i, 0) + q
        recs = list(agg.items())
        if len(recs) > 1:
            main = [x for x in recs if x[0] not in MG]
            if main:
                recs = main
        if all(x[0] in MG for x in recs) and kind in ('ship', 'sub') and big:
            continue
        arc = hc_arc(m['arcs'])
        mname = m['name']
        cap = int(fnum(m['cap']))
        rof = int(fnum(m['rof']))
        auto = int(m['auto'] == '1')
        is_vls = bool(re.search(r'VLS|Mk ?41|Mk ?57|Mk ?25|Mk ?48 ', mname, re.I)) and len(recs) >= 1 and classify(recs[0][0]) in ('d1', 'e1')
        if len(recs) > 4:
            recs = consolidate(recs)
        if len(recs) > 4:
            # split into several mounts of <=4 weapon types, cells proportional to rounds
            chunks = [recs[i:i + 4] for i in range(0, len(recs), 4)]
            tot = sum(q for _, q in recs)
            for ch in chunks:
                sub = dict(m)
                sub['weapons'] = []
                sub['cap'] = str(max(1, round(int(fnum(m['cap'])) * sum(q for _, q in ch) / tot)))
                sub['_recs'] = ch
                PENDING.append(sub)
            continue
        if len(recs) > 1:
            # multi-weapon group -> z2
            zid = A.get('z2')
            NEW['z2'].append({'id': str(zid), 'weapon_array': L.mkarr([r[0] for r in recs]),
                              'weapqty_array': L.mkarr([min(255, r[1]) for r in recs])})
            wep = zid
            rounds = min(255, sum(r[1] for r in recs))
        else:
            wep = recs[0][0]
            rounds = min(255, recs[0][1])
        # try reuse identical existing mount from analog
        reuse = None
        for mid in L.arr(analog['mount_array']):
            z = HROW[('z1', mid)]
            if int(z['wepid']) == wep and int(z['arc']) == arc and mid not in used_hc:
                reuse = mid
                break
        if reuse:
            used_hc.add(reuse)
            out.append(reuse)
            continue
        cav = cavity_for(recs[0][0], mname)
        a0 = classify(recs[0][0])
        ntubes = cap if cav in (0, 1, 4) else 1
        if a0 == 'c1':
            ntubes = 1
        tgts = 1
        if cav == 4:
            tgts = 6 if a0 == 'd1' else 2
        elif cav == 5:
            tgts = 2
        elif cav == 1:
            tgts = 1
        rate = {0: 1, 1: 15, 2: 16, 3: 1, 4: 15, 5: 3}.get(cav, 1)
        if a0 == 'c1' and cav == 2:
            rate = max(1, min(30, rof // 4 if rof > 30 else rof)) if rof else 16
        dfl = mount_defaults(base_weapon(recs[0][0]))
        if dfl:
            tgts = int(dfl['numtargets']); rate = int(dfl['ratoffire']); auto = int(dfl['autonomous'])
            cav = int(dfl['cavitylabel'])
            if re.search(r'VLS|Cells', mname, re.I) and kind == 'ship':
                cav = 4
            if a0 == 'c1':
                ntubes = 1
        label = re.sub(r'\s+', ' ', mname).replace(',', ';').replace('"', '')[:40]
        zrow = {'location': '0', 'wepid': str(wep), 'arc': str(arc), 'nummounts': '1',
                'numroundsmnt': str(rounds), 'numtubes': str(max(1, min(255, ntubes))), 'numtargets': str(tgts),
                'ratoffire': str(rate), 'autonomous': str(auto), 'cavitylabel': str(cav),
                'mntarmor': '0', 'classname': label}
        zkey = tuple(sorted(zrow.items()))
        if zkey in ZCACHE:
            out.append(ZCACHE[zkey])
            continue
        zid = A.get('z1')
        ZCACHE[zkey] = zid
        NEW['z1'].append({'id': str(zid), 'location': '0', 'wepid': str(wep), 'arc': str(arc), 'nummounts': '1',
                          'numroundsmnt': str(rounds), 'numtubes': str(max(1, min(255, ntubes))), 'numtargets': str(tgts),
                          'ratoffire': str(rate), 'autonomous': str(auto), 'cavitylabel': str(cav),
                          'mntarmor': '0', 'classname': label})
        out.append(zid)
    if not navdecoy and kind == 'ship':
        # still keep analog decoys for combatants
        pass
    out += [s for s in struct if s not in out]
    return out[:40]


def mount_weapons(zids):
    ws = set()
    for z in zids:
        r = HROW.get(('z1', z)) or next((x for x in NEW['z1'] if int(x['id']) == z), None)
        if not r:
            continue
        w = int(r['wepid'])
        ws.add(w)
        g = HROW.get(('z2', w)) or next((x for x in NEW['z2'] if int(x['id']) == w), None)
        if g:
            ws |= set(L.arr(g['weapon_array']))
    return ws


def build_mags(Pl, fireable=None):
    out = []
    agg = collections.OrderedDict()
    for m in Pl['mags']:
        if m['aviation'] == '1':
            continue
        cap = int(fnum(m['cap'])) or 10 ** 6
        for w in reversed(m['weapons']):
            if not w['load'] or cap <= 0:
                continue
            r = hc_weapon(w['wid'], w['load'])
            if not r:
                continue
            a = classify(r[0])
            if a not in ('c1', 'd1', 'e1', 'f1') or r[0] in MG:
                continue
            if fireable is not None and r[0] not in fireable:
                continue
            q = min(r[1], cap)
            cap -= q
            agg[r[0]] = agg.get(r[0], 0) + q
    for wid, cnt in agg.items():
        while cnt > 0:
            c = min(cnt, 255)
            out.append(add_mag(wid, c, 5))
            cnt -= c
    return out[:24]


def build_sensors(Pl):
    out = []
    ids = list(Pl['sensors'])
    for m in Pl['mounts']:
        ids += m['sensors']
    for s in ids:
        h = hc_sensor(s)
        if h and h not in out:
            out.append(h)
    # radars first
    out.sort(key=lambda i: 0 if 40960 <= i < 45056 else 1)
    return out[:12]


def ship_dp(disp, core, extra_mult=1.0):
    T = disp
    if T <= 500:
        dp = T / 20
    elif T <= 5000:
        dp = T / 30 + 9
    elif T <= 12000:
        dp = T / 50 + 76
    else:
        dp = T / 60 + 116
    return int(math.ceil(dp * extra_mult))


def detectsize(dp):
    return 2 if dp < 50 else 3 if dp < 140 else 5 if dp < 450 else 7 if dp <= 1200 else 10


def max_speed(Pl):
    sp = 0
    for p in Pl['prop']:
        for x in p['perf']:
            sp = max(sp, int(fnum(x['Speed'])))
    return sp


PROP = {'3001': 68, '3002': 71, '3003': 83, '3004': 78, '3005': 71, '3006': 68}


def prop_code(Pl, default):
    t = [p['type'] for p in Pl['prop']]
    names = ' '.join(p['name'] for p in Pl['prop']).lower()
    if 'nuclear' in names or 'reactor' in names:
        return 78
    if 'gas turbine' in names or ' gt' in names or 'lm2500' in names or 'mt30' in names or 'turbine' in names:
        return 71
    if 'steam' in names:
        return 83
    if 'diesel' in names:
        return 68
    return default


# ------------------------------------------------------------------ descriptions
def fmt_list(xs):
    xs = [x for x in xs if x]
    return ', '.join(xs[:-1]) + (' and ' + xs[-1] if len(xs) > 1 else (xs[0] if xs else ''))


def describe(Pl, hcname, arms, sens):
    c = Pl['core']
    comments = c.get('Comments', '')
    yr = Pl['year']
    t = f"{hcname}: {Pl['country'].split(' [')[0]} {Pl['cmoname']} as configured c.{yr}"
    if comments and comments not in ('-', ''):
        t += f' ({comments})'
    t += '. '
    if arms:
        t += 'Armament: ' + fmt_list(arms) + '. '
    if sens:
        t += 'Sensors: ' + fmt_list(sens) + '. '
    t += 'Converted from Command: Modern Operations DB3000 data for HCDB (2026).'
    return t


# ------------------------------------------------------------------ analogs
ANALOG = {
    'ship|CG Ticonderoga Baseline 2': 'Bunker Hill (CM)', 'ship|CG Ticonderoga Baseline 3': 'Bunker Hill (CM)',
    'ship|CG Ticonderoga Baseline 4': 'Bunker Hill (CM)',
    'ship|CVN Gerald R. Ford': 'Gerald R. Ford', 'ship|CVN Nimitz': 'Stennis (2005)',
    'ship|DDG Arleigh Burke Flight I': 'Arleigh Burke', 'ship|DDG Arleigh Burke Flight II': 'Arleigh Burke',
    'ship|DDG Arleigh Burke Flight IIA': 'Arleigh Burke IIA', 'ship|DDG Arleigh Burke Flight IIA Restart': 'Arleigh Burke IIA',
    'ship|DDG Arleigh Burke Flight IIA Technology Insertion': 'Arleigh Burke IIA',
    'ship|DDG Arleigh Burke Flight III': 'Arleigh Burke IIA', 'ship|DDG Zumwalt': 'Zumwalt',
    'ship|EPF Spearhead Flight II': 'Spearhead JHSV', 'ship|ESB Montford Point Mod': 'Montford Point',
    'ship|FFG Constellation': 'Bergamini FREMM', 'ship|LCAC SSC': 'LCAC',
    'ship|LCS Freedom': 'Freedom ASW', 'ship|LCS Independence': 'Independence SUW',
    'ship|LHA America Flight 0': 'America (LHA-R)', 'ship|LHA America Flight I': 'America (LHA-R)',
    'ship|LHD Wasp': 'Makin Island', 'ship|LPD San Antonio Flight I': 'San Antonio',
    'ship|LPD San Antonio Flight II': 'San Antonio', 'ship|LSD Whidbey Island': 'Whidbey Island (01)',
    'ship|LSD Whidbey Island Mod': 'Harpers Ferry (99)', 'ship|T-AO John Lewis': 'Henry J. Kaiser',
    'ship|WMSM Heritage': 'Legend',
    'sub|SSBN Columbia': 'Ohio (2010)', 'sub|SSBN Ohio': 'Ohio (2010)', 'sub|SSGN Ohio': 'Ohio SSGN',
    'sub|SSN Los Angeles Flight II': 'Providence (688I/03)', 'sub|SSN Los Angeles Flight III, 688i': 'San Juan (688I/98)',
    'sub|SSN Virginia Blk I/II': 'Virginia (Flight II)', 'sub|SSN Virginia Blk III/IV': 'Virginia (Flight III)',
    'sub|SSN Virginia Blk V': 'Virginia (Flight III)',
    'air|A-10C Thunderbolt II': 'A-10C Warthog', 'air|AH-1Z Viper': 'AH-1Z Viper', 'air|AH-64E Apache Guardian': 'AH-64E Guardian',
    'air|AV-8B Harrier II+ [Night Attack]': 'AV-8B Harrier II Plus', 'air|B-1B Lancer': 'B-1B Lancer',
    'air|B-21 Raider': 'B-2A Spirit Blk30', 'air|B-2A Spirit': 'B-2A Spirit Blk30', 'air|B-52H Stratofortress': 'B-52H Stratofortress',
    'air|CH-53E Super Stallion': 'CH-53E Super Stallion', 'air|CH-53K King Stallion': 'CH-53K King Stallion',
    'air|CMV-22B Osprey': 'MV-22B Osprey', 'air|E-2D Advanced Hawkeye': 'E-2D Hawkeye', 'air|E-3G Sentry': 'E-3C Sentry RSIP',
    'air|EA-18G Growler': 'EA-18G Growler', 'air|EA-37B Compass Call': 'EC-130H Compass Call',
    'air|F-15C Eagle': 'F-15C Eagle Blk39', 'air|F-15CX Advanced Eagle': 'F-15C Eagle Blk39',
    'air|F-15E Strike Eagle': 'F-15E Strike Eagle', 'air|F-15EX Eagle II': 'F-15E Strike Eagle',
    'air|F-16C Blk 30/32': 'F-16C/D Blk30/32', 'air|F-16CM Blk 40/42': 'F-16C/D Blk40/42 CCIP',
    'air|F-16CM Blk 50/52': 'F-16C/D Blk50/52 CCIP', 'air|F-22A Raptor': 'F-22A Raptor Blk30/35',
    'air|F-35A Lightning II': 'F-35C Lightning II', 'air|F-35B Lightning II': 'F-35C Lightning II',
    'air|F-35C Lightning II': 'F-35C Lightning II', 'air|F/A-18A+ Hornet': 'F/A-18A+ Hornet',
    'air|F/A-18C Hornet': 'F/A-18C (USN/PCW)', 'air|F/A-18E Super Hornet Blk II': 'F/A-18E Block II',
    'air|F/A-18E Super Hornet Blk III': 'F/A-18E Block II', 'air|F/A-18F Super Hornet Blk II': 'F/A-18F Block II',
    'air|F/A-18F Super Hornet Blk III': 'F/A-18F Block II', 'air|KC-135R Stratotanker': 'KC-135R Stratotanker',
    'air|KC-46A Pegasus': 'KC-46A', 'air|MH-53E Sea Dragon': 'MH-53E Sea Dragon', 'air|MH-60R Seahawk': 'MH-60R Seahawk',
    'air|MH-60S Seahawk': 'MH-60S Seahawk', 'air|MQ-1C ER Gray Eagle UAV': 'MQ-1C Gray Eagle',
    'air|MQ-25A Stingray UAV': 'X-45C Phantom Ray', 'air|MQ-4C Triton UAV': 'MQ-4C Triton',
    'air|MQ-58B Valkyrie': 'X-45C Phantom Ray', 'air|MQ-8B Fire Scout UAV': 'MQ-8B Fire Scout',
    'air|MQ-8C Fire Scout UAV': 'MQ-8B Fire Scout', 'air|MQ-9A Reaper UAV': 'MQ-9A Reaper', 'air|MV-22B Osprey': 'MV-22B Osprey',
    'air|OA-1K Skyraider II': 'OV-10D Bronco', 'air|P-8A Poseidon': 'P-8A Poseidon', 'air|P-8A Poseidon [AAS]': 'P-8A Poseidon',
    'air|P-8A Poseidon [LSRS]': 'P-8A Poseidon', 'air|RC-135W Rivet Joint': 'RC-135W Rivet Joint',
    'air|RQ-180 UAV': 'RQ-170 Sentinel', 'air|RQ-4B Global Hawk UAV': 'RQ-4B Global Hawk Blk20',
    'air|U-2S Senior Year': 'U-2S Dragon Lady', 'air|UH-1Y Venom': 'UH-1Y Venom',
}

SHIPTYPE_IDX = {n: i for i, n in enumerate(BS['ShipType']) if n}


def hc_platform_name(Pl):
    key = Pl['key']
    y = Pl['year']
    if Pl['kind'] == 'air':
        n = key.replace(' UAV', '').replace(' [Night Attack]', ' (NA)')
        n = re.sub(r'\s*\[(.*)\]', r' \1', n)
    else:
        n = key.split(' ', 1)[1]
        n = n.replace('Arleigh Burke Flight IIA Technology Insertion', 'Burke IIA Tech Insertion')
        n = n.replace('Arleigh Burke Flight IIA Restart', 'Burke IIA Restart')
        n = n.replace('Arleigh Burke Flight', 'Arleigh Burke')
        n = n.replace('Ticonderoga Baseline', 'Ticonderoga BL')
        n = n.replace('Los Angeles Flight III, 688i', 'Los Angeles 688i')
        n = n.replace('Los Angeles Flight II', 'Los Angeles VLS')
        n = n.replace('Montford Point Mod', 'Lewis B. Puller ESB').replace('Spearhead Flight II', 'Spearhead EPF II')
        n = n.replace('Whidbey Island Mod', 'Harpers Ferry')
        if Pl['key'].startswith('SSGN'):
            n = 'Ohio SSGN'
    n = n.replace('San Antonio Flight', 'San Antonio Flt').replace('Lewis B. Puller ESB', 'Lewis B. Puller')
    return f'{n} ({y})'


# ------------------------------------------------------------------ class names (hull names) from CMO
def cmo_hull_names(Pl):
    key = Pl['key']
    tab = 'Ships' if Pl['kind'] == 'ship' else 'Submarines'
    import selplat as _s  # noqa
    names = []
    for r in D['flat'][tab].values():
        if r['Country'] != 'United States':
            continue
        if _s.key(Pl['kind'], r['Name'], r['Type']) == key:
            m = re.match(r'^(?:T-)?[A-Z]{2,5}\s*(\d+)\s+(.*?)(?:\s*\[.*\])?$', r['Name'])
            if m:
                names.append(m.group(2).strip())
    return list(dict.fromkeys(names))


EXTRA_NAMES = {
    'DDG Arleigh Burke Flight IIA Restart': ['John Finn', 'Ralph Johnson', 'Rafael Peralta'],
    'DDG Arleigh Burke Flight IIA Technology Insertion': ['Thomas Hudner', 'Paul Ignatius', 'Daniel Inouye', 'Delbert D. Black', 'Carl M. Levin', 'Frank E. Petersen Jr.', 'Lenah H. Sutcliffe Higbee', 'John Basilone', 'Harvey C. Barnum Jr.', 'Patrick Gallagher'],
    'DDG Arleigh Burke Flight III': ['Jack H. Lucas', 'Louis H. Wilson Jr.', 'Ted Stevens', 'Jeremiah Denton', 'William Charette', 'George M. Neal', 'Quentin Walsh', 'Sam Nunn', 'John F. Lehman', 'Thad Cochran', 'Richard G. Lugar'],
    'FFG Constellation': ['Constellation', 'Congress'],
    'SSBN Columbia': ['District of Columbia', 'Wisconsin'],
    'SSGN Ohio': ['Ohio', 'Michigan', 'Florida', 'Georgia'],
    'SSN Virginia Blk I/II': ['Virginia', 'Texas', 'Hawaii', 'North Carolina', 'New Hampshire', 'New Mexico', 'Missouri', 'California', 'Mississippi', 'Minnesota'],
    'SSN Virginia Blk III/IV': ['North Dakota', 'John Warner', 'Illinois', 'Washington', 'Colorado', 'Indiana', 'South Dakota', 'Delaware', 'Vermont', 'Oregon', 'Montana', 'Hyman G. Rickover', 'New Jersey', 'Iowa', 'Massachusetts', 'Idaho', 'Arkansas', 'Utah'],
    'SSN Virginia Blk V': ['Oklahoma', 'Arizona', 'Barb', 'Tang', 'Wahoo'],
    'LHA America Flight 0': ['America', 'Tripoli'],
    'LHA America Flight I': ['Bougainville', 'Fallujah'],
    'LPD San Antonio Flight II': ['Harrisburg', 'Pittsburgh'],
    'WMSM Heritage': ['Argus', 'Chase', 'Ingham', 'Rush'],
    'T-AO John Lewis': ['John Lewis', 'Oscar V. Peterson', 'Earl Warren', 'Robert F. Kennedy', 'Lucy Stone', 'Sojourner Truth'],
    'ESB Montford Point Mod': ['Lewis B. Puller', 'Hershel Woody Williams', 'Miguel Keith', 'John L. Canley', 'Robert E. Simanek'],
    'LCS Freedom': ['Freedom', 'Fort Worth', 'Milwaukee', 'Detroit', 'Little Rock', 'Sioux City', 'Wichita', 'Billings', 'Indianapolis', 'St. Louis', 'Minneapolis-Saint Paul', 'Cooperstown', 'Marinette', 'Nantucket', 'Beloit', 'Cleveland'],
    'LCS Independence': ['Independence', 'Coronado', 'Jackson', 'Montgomery', 'Gabrielle Giffords', 'Omaha', 'Manchester', 'Tulsa', 'Charleston', 'Cincinnati', 'Kansas City', 'Oakland', 'Mobile', 'Savannah', 'Canberra', 'Santa Barbara', 'Augusta', 'Kingsville', 'Pierre'],
}
SAME_CLASS_ANALOG = ('Arleigh Burke', 'Arleigh Burke IIA', 'Bunker Hill (CM)', 'Stennis (2005)', 'Gerald R. Ford', 'Makin Island',
                     'San Antonio', 'Whidbey Island (01)', 'Harpers Ferry (99)', 'Ohio (2010)', 'Providence (688I/03)',
                     'San Juan (688I/98)', 'Virginia (Flight II)')


def class_names(Pl, analog):
    key = Pl['key']
    names = list(EXTRA_NAMES.get(key, []))
    names += cmo_hull_names(Pl)
    aname = ANALOG[Pl['kind'] + '|' + key]
    if aname in SAME_CLASS_ANALOG and key not in ('SSBN Columbia', 'DDG Arleigh Burke Flight III',
                                                  'DDG Arleigh Burke Flight IIA Restart', 'DDG Arleigh Burke Flight IIA Technology Insertion'):
        an = SHIPNAMES.get(int(analog['id']))
        if an:
            names += [x.strip('"') for x in an['count:names'].split(':')[1:]]
    names = [n for n in names if not re.match(r'^[A-Z]{2,5}\s*\d+$', n.strip()) and n.strip() != 'John F. Kenney']
    out = list(dict.fromkeys(n.strip() for n in names if n.strip()))
    return out or [hc_platform_name(Pl).split(' (')[0]]


# ================================================================== SHIPS / SUBS
def build_surface(Pl):
    analog = pick_analog(Pl)
    c = Pl['core']
    row = dict(analog)
    row['id'] = str(A.get('a1'))
    name = hc_platform_name(Pl)
    row['classname'] = name
    newclass = True
    if newclass:
        disp = int(fnum(c['DisplacementEmpty']) or fnum(c['DisplacementStandard']) * 0.85 or fnum(c['DisplacementFull']) * 0.75)
        mult = 1.0
        if re.match(r'(AOR|AOE|AO|AFS) ', E['EnumShipType'].get(c['Type'], '')):
            mult *= 0.75
        if Pl['country'].startswith(('Russia', 'North Korea')):
            mult *= 0.9
        if Pl['key'].startswith(('EPF', 'LCAC', 'ESB')):
            mult *= 0.5
        row['origdp'] = str(max(1, ship_dp(disp, c, mult)))
    else:
        disp = int(analog['displacement'])
        if Pl['key'].endswith('Flight III'):
            disp += 200
        row['origdp'] = str(int(analog['origdp']) + (4 if Pl['key'].endswith('Flight III') else 0))
    row['displacement'] = str(disp)
    row['detectsize'] = str(detectsize(int(row['origdp'])))
    row['length'] = str(int(round(fnum(c['Length']) or fnum(analog['length']))))
    sp = max_speed(Pl)
    if sp:
        a_sp = int(analog['maxspeed'])
        same = False
        row['maxspeed'] = str(min(sp, a_sp + 1) if same and a_sp else sp)
    row['propulsion'] = str(prop_code(Pl, int(analog['propulsion'])))
    st = E['EnumShipType'].get(c['Type'], '').split(' -')[0].strip()
    if st in SHIPTYPE_IDX:
        row['subtype'] = str(SHIPTYPE_IDX[st])
    elif st == 'LCS':
        pass
    row['country'] = str(CTRY(Pl))
    mounts = build_mounts(Pl, analog, 'ship', big=int(row['origdp']) > 100)
    row['mount_array'] = L.mkarr(mounts)
    sens = build_sensors(Pl)
    row['sensor_array'] = L.mkarr(sens)
    mags = build_mags(Pl, mount_weapons(mounts))
    row['mag_array'] = L.mkarr(mags)
    # hangar capacity from CMO aircraft facilities
    hang = 0
    for f in Pl.get('facilities', []):
        ft = E['EnumAircraftFacilityType'].get(f.get('Type', ''), '')
        if 'Hangar' in ft or 'Hangar' in f.get('Name', ''):
            hang += int(fnum(f.get('Capacity', 0)))
    if hang and int(analog['planecapacity']) < 20:
        row['planecapacity'] = str(min(hang, 255))
    arms = sorted({weapon_name(HROW[('z1', m)]['wepid'] if ('z1', m) in HROW else 0) for m in []})
    arms = [n['name'] for n in Pl['mounts'] if any(maps.W.get(str(w['wid']), AUTO_W.get(str(w['wid']))) not in (None, 'SKIP', 'NAVDECOY') for w in n['weapons'])]
    sens_n = [D['Sensor'][s]['Name'] for s in Pl['sensors'] if s in maps.S or s in AUTO_S][:8]
    row['textindex'] = str(add_string(describe(Pl, name, list(dict.fromkeys(arms))[:10], sens_n)))
    NEW['a1'].append(row)
    add_names(int(row['id']), class_names(Pl, analog))
    LOG.append(('ship', name, 'a1', row['id'], f"analog {analog['classname']}; disp {disp}t DP {row['origdp']} spd {row['maxspeed']}kt; mounts {len(mounts)} sensors {len(sens)} mags {len(mags)}", Pl['cmoname']))


def build_sub(Pl):
    analog = pick_analog(Pl)
    c = Pl['core']
    row = dict(analog)
    row['id'] = str(A.get('a2'))
    name = hc_platform_name(Pl)
    row['classname'] = name
    disp = int(fnum(c['DisplacementStandard']) or fnum(c['DisplacementFull']) or fnum(analog['displacement']))
    row['displacement'] = str(disp)
    # keep analog DP ratio (subs use different rules); scale by displacement
    row['origdp'] = str(max(1, int(round(int(analog['origdp']) * (disp / max(1, int(analog['displacement']))) ** 0.5))))
    row['detectsize'] = analog['detectsize']
    row['length'] = str(int(round(fnum(c['Length']) or fnum(analog['length']))))
    sub_sp = 0
    surf_sp = 0
    for p in Pl['prop']:
        for x in p['perf']:
            ab = int(fnum(x['AltitudeBand']))
            s = int(fnum(x['Speed']))
            sub_sp = max(sub_sp, s)
    if sub_sp:
        row['maxsubspeed'] = str(sub_sp)
    row['country'] = str(CTRY(Pl))
    mounts = build_mounts(Pl, analog, 'sub')
    row['mount_array'] = L.mkarr(mounts)
    sens = build_sensors(Pl)
    row['sensor_array'] = L.mkarr(sens)
    # Harpoon subs carry reloads in the tube mount: consolidate tubes + magazine load-out
    tube_ids = [z for z in mounts if (next((x for x in NEW['z1'] if int(x['id']) == z), None) or HROW.get(('z1', z), {})).get('classname', '').find('TT') >= 0]
    if tube_ids:
        ntubes = len(tube_ids)
        load = collections.OrderedDict()
        for m in Pl['mounts']:
            if 'TT' in m['name'] or 'Torpedo' in m['name']:
                for w in m['weapons']:
                    if w['load']:
                        r = hc_weapon(w['wid'], w['load'])
                        if r:
                            load[r[0]] = load.get(r[0], 0) + r[1]
        for mg in Pl['mags']:
            for w in mg['weapons']:
                if w['load']:
                    r = hc_weapon(w['wid'], w['load'])
                    if r and classify(r[0]) in ('f1', 'd1', 'e1'):
                        load[r[0]] = load.get(r[0], 0) + r[1]
        items = list(load.items())
        if len(items) > 1:
            gid = A.get('z2')
            NEW['z2'].append({'id': str(gid), 'weapon_array': L.mkarr([a for a, _ in items]), 'weapqty_array': L.mkarr([min(255, b) for _, b in items])})
            wep = gid
        else:
            wep = items[0][0]
        zid = A.get('z1')
        NEW['z1'].append({'id': str(zid), 'location': '0', 'wepid': str(wep), 'arc': '3591', 'nummounts': '1',
                          'numroundsmnt': str(min(255, sum(b for _, b in items))), 'numtubes': str(ntubes), 'numtargets': '2',
                          'ratoffire': '2', 'autonomous': '0', 'cavitylabel': '0', 'mntarmor': '0',
                          'classname': f'533mm TT x{ntubes} ' + name.split(' (')[0][:20]})
        mounts = [z for z in mounts if z not in tube_ids] + [zid]
        row['mount_array'] = L.mkarr(mounts)
    mags = []
    arms = list(dict.fromkeys(n['name'] for n in Pl['mounts'] if any(maps.W.get(str(w['wid']), AUTO_W.get(str(w['wid']))) not in (None, 'SKIP', 'NAVDECOY') for w in n['weapons'])))
    sens_n = [D['Sensor'][s]['Name'] for s in Pl['sensors'] if s in maps.S or s in AUTO_S][:8]
    row['textindex'] = str(add_string(describe(Pl, name, arms[:10], sens_n)))
    NEW['a2'].append(row)
    add_names(int(row['id']), class_names(Pl, analog))
    LOG.append(('sub', name, 'a2', row['id'], f"analog {analog['classname']}; disp {disp}t DP {row['origdp']} spd {row['maxsubspeed']}kt; mounts {len(mounts)} sensors {len(sens)} mags {len(mags)}", Pl['cmoname']))


# ================================================================== AIRCRAFT
ROLE2MISSION = {
    '2001': 15, '2002': 15, '2003': 16, '2004': 16, '2005': 15, '2006': 15, '2007': 16,
    '3001': 11, '3002': 10, '3003': 7, '3004': 22, '3005': 7,
    '3101': 11, '3102': 10, '3103': 7, '3104': 22, '3105': 7,
    '3201': 5, '3202': 6, '3203': 7, '3204': 22, '3205': 7,
    '3401': 20, '4001': 3, '4002': 3, '4003': 3, '4004': 22, '4005': 3,
    '4201': 114, '4202': 114, '4301': 11, '6001': 17, '6002': 17,
    '7001': 113, '7002': 113, '7003': 14, '7004': 113, '7005': 3,
    '7101': 1, '7102': 1, '7201': 0, '8001': 2, '9001': 24, '9004': 24,
}
PRIORITY = [15, 16, 5, 6, 7, 10, 11, 9, 20, 14, 17, 22, 2, 3, 113, 114, 1, 0, 4, 24]


def is_gun(hc):
    return classify(hc) == 'c1'


def build_aircraft(Pl):
    analog = pick_analog(Pl)
    c = Pl['core']
    row = dict(analog)
    row['id'] = str(A.get('b1'))
    name = hc_platform_name(Pl)
    row['classname'] = name
    row['country'] = str(CTRY(Pl))
    sens = build_sensors(Pl)
    if sens:
        row['sensor_array'] = L.mkarr(sens)
    # guns carried as internal mounts
    guns = []
    for m in Pl['mounts']:
        for w in m['weapons']:
            r = hc_weapon(w['wid'], 3)
            if r and is_gun(r[0]):
                guns.append(r[0])
    gun = guns[0] if guns else None
    # analog loadout info
    a_lo = [HROW[('y1', l)] for l in L.arr(analog['Loadout_array'])]
    a_max_rng = max([int(y['range']) for y in a_lo] or [int(analog['range'])])
    a_data = {int(y['mission']): y['DATA'] for y in a_lo}
    a_default_data = a_lo[0]['DATA'] if a_lo else '30'
    # candidate loadouts
    cands = []
    maxrad = max([int(fnum(l['radius'])) for l in Pl.get('loadouts', [])] or [0]) or 1
    for l in Pl.get('loadouts', []):
        mis = ROLE2MISSION.get(l['role'])
        if mis is None:
            continue
        agg = collections.OrderedDict()
        for w in l['weapons']:
            r = hc_weapon(w['wid'], w['load'] or 1)
            if not r:
                continue
            agg[r[0]] = agg.get(r[0], 0) + r[1]
        if gun and mis not in (0, 1, 2, 24, 113, 114, 3, 17) and gun not in agg:
            agg[gun] = 3
        wl = [(k, min(v, 255)) for k, v in agg.items()]
        if not wl and mis not in (0, 1, 2, 3, 24, 113):
            continue
        sig = tuple(sorted(k for k, _ in wl if not is_gun(k)))
        cands.append((mis, sig, wl, int(fnum(l['radius'])), l['name']))
    # choose up to 10: one per (mission, weapon-signature), prioritise mission variety
    chosen, seen = [], set()
    for rnd in range(3):
        for mis in PRIORITY:
            for cd in cands:
                if cd[0] != mis or (cd[0], cd[1]) in seen:
                    continue
                cnt = sum(1 for x in chosen if x[0] == mis)
                if cnt > rnd:
                    continue
                seen.add((cd[0], cd[1]))
                chosen.append(cd)
                break
            if len(chosen) >= 6:
                break
        if len(chosen) >= 6:
            break
    if not chosen:  # fall back to analog loadouts
        lo_ids = L.arr(analog['Loadout_array'])
    else:
        lo_ids = []
        a_by_mis = {}
        for y in a_lo:
            mm = int(y['mission'])
            a_by_mis[mm] = max(a_by_mis.get(mm, 0), int(y['range']))
        nonferry = sorted(int(y['range']) for y in a_lo if int(y['mission']) not in (24, 77))
        a_med = nonferry[len(nonferry) // 2] if nonferry else int(int(analog['range']) * 0.4)
        crad = sorted(c[3] for c in chosen if c[0] != 24 and c[3])
        c_med = crad[len(crad) // 2] if crad else 0
        by_mis_rad = collections.defaultdict(list)
        for c_ in chosen:
            if c_[3]:
                by_mis_rad[c_[0]].append(c_[3])
        for mis, sig, wl, rad, lname in chosen:
            yid = A.get('y1')
            if mis == 24:
                rng = a_by_mis.get(24, int(analog['range']))
            elif mis in a_by_mis:
                mr = sorted(by_mis_rad[mis])
                f = (rad / mr[len(mr) // 2]) if rad and mr else 1.0
                rng = a_by_mis[mis] * max(0.7, min(1.3, f))
            else:
                f = (rad / c_med) if rad and c_med else 1.0
                rng = a_med * max(0.5, min(2.0, f))
            rng = int(max(50, min(round(rng), 30000)))
            if mis == 2 and not any(w == 30902 for w, _ in wl):
                wl = [(30902, 1)] + wl
            NEW['y1'].append({'id': str(yid), 'weapon_array': L.mkarr([w for w, _ in wl]), 'range': str(rng),
                              'mission': str(mis), 'weapqty_array': L.mkarr([q for _, q in wl]),
                              'DATA': a_data.get(mis, a_default_data)})
            lo_ids.append(yid)
    row['Loadout_array'] = L.mkarr(lo_ids)
    # flags per variant
    fl = int(analog['unitflags'])
    if Pl['key'].startswith('F-35A'):
        fl &= ~(1 << 15)
        row['runway'] = '5'
        row['propulsion'] = '5'
    if Pl['key'].startswith('F-35B'):
        row['runway'] = '3'
        row['propulsion'] = '9' if False else '7'
    codes = [E['EnumAircraftCode'].get(x, '') for x in Pl['codes']]
    cj = ' '.join(codes)
    if 'IRST' in cj:
        fl |= 1
    if 'FLIR' in cj:
        fl |= 1 << 3
    if 'Refuel' in cj or 'Refueling' in cj:
        fl |= 1 << 12
    if any(E['EnumSensorType'].get(D['Sensor'][s]['Type'], '') == 'ESM' for s in Pl['sensors']):
        fl |= 1 << 6
    if any(E['EnumSensorType'].get(D['Sensor'][s]['Type'], '') == 'MAD' for s in Pl['sensors']):
        fl |= 1 << 1
    row['unitflags'] = str(fl)
    arms = []
    for mis, sig, wl, rad, lname in chosen:
        arms += [weapon_name(w) for w, _ in wl if not is_gun(w)]
    arms = list(dict.fromkeys(arms))[:12]
    sens_n = [D['Sensor'][s]['Name'] for s in Pl['sensors'] if s in maps.S or s in AUTO_S][:6]
    row['textindex'] = str(add_string(describe(Pl, name, arms, sens_n)))
    NEW['b1'].append(row)
    LOG.append(('aircraft', name, 'b1', row['id'], f"analog {analog['classname']}; loadouts {len(lo_ids)} (of {len(cands)} CMO candidates); sensors {len(sens)}", Pl['cmoname']))


NAMELIM = {'a1': 25, 'a2': 24, 'b1': 23, 'c1': 26, 'd1': 27, 'e1': 25, 'f1': 19, 'g1': 25, 'g2': 23, 'j1': 27, 'm1': 29, 'z1': 29}
NICK = ['Thunderbolt II', 'Apache Guardian', 'Harrier II+', 'Stratofortress', 'Super Stallion', 'King Stallion',
        'Advanced Hawkeye', 'Compass Call', 'Advanced Eagle', 'Strike Eagle', 'Eagle II', 'Lightning II', 'Super Hornet',
        'Stratotanker', 'Sea Dragon', 'Gray Eagle', 'Skyraider II', 'Rivet Joint', 'Global Hawk', 'Senior Year']
PRI = {'d1': 0, 'e1': 0, 'f1': 0, 'g1': 1, 'c1': 2, 'g2': 3, 'm1': 1}


def shorten(k, n):
    lim = NAMELIM[k]
    if len(n) <= lim:
        return n
    m = re.match(r'^(.*?)\s*(\(\d{4}\))$', n)
    base, yr = (m.group(1), ' ' + m.group(2)) if m else (n, '')
    base = re.sub(r'\s*\[.*?\]', '', base)
    for nk in NICK:
        if len(base) + len(yr) <= lim:
            break
        base = base.replace(' ' + nk, '').replace(nk, '')
    base = base.replace('Virginia Blk ', 'Virginia ').replace('Poseidon', '').replace('Mod ', 'Mod').replace('  ', ' ').strip()
    if len(base) + len(yr) > lim:
        base = base[:lim - len(yr)].rstrip()
    return base + yr


def prune():
    used_z1, used_z2 = set(), set()
    for k in ('a1', 'a2'):
        for r in NEW[k]:
            used_z1 |= set(L.arr(r['mount_array']))
    for r in NEW['z1']:
        used_z2.add(int(r['wepid']))
    NEW['z1'][:] = [r for r in NEW['z1'] if int(r['id']) in used_z1]
    NEW['z2'][:] = [r for r in NEW['z2'] if int(r['id']) in used_z2]
    used_m = set()
    for r in NEW['a1']:
        used_m |= set(L.arr(r['mag_array']))
    NEW_MAGS[:] = [m for m in NEW_MAGS if m[0] in used_m]


def conform():
    prune()
    for r in NEW['z1']:
        r['classname'] = re.sub(r'\s*\[.*?\]', '', r['classname']).replace(' CIWS', '').replace('Naval Strike Missile (NSM)', 'NSM').strip() or r['classname']
    for k, rows in NEW.items():
        for r in rows:
            if 'classname' in r:
                r['classname'] = shorten(k, r['classname'].replace(',', ';'))
    for r in NEW['d1']:
        r['speed'] = str(min(9999, int(r['speed'])))
    for r in NEW['z1']:
        r['numtubes'] = str(min(80, int(r['numtubes'])))
    for r in NEW['y1']:
        w = L.arr(r['weapon_array'])
        q = L.arr(r['weapqty_array'])
        if len(w) > 8:
            items = sorted(zip(w, q), key=lambda x: PRI.get(classify(x[0]) or 'm1', 1))[:8]
            keep = set(i for i, _ in items)
            pairs = [(a, b) for a, b in zip(w, q) if a in keep]
            r['weapon_array'] = L.mkarr([a for a, _ in pairs])
            r['weapqty_array'] = L.mkarr([b for _, b in pairs])



# ================================================================== foreign-batch overrides
CMAP = {'China': 'China', 'Russia [1992-]': 'Russia', 'North Korea': 'North Korea', 'South Korea': 'South Korea', 'Japan': 'Japan',
        'Albania': 'Albania', 'Belgium': 'Belgium', 'Bulgaria': 'Bulgaria', 'Canada': 'Canada', 'Croatia [1992-]': 'Croatia',
        'Czech Republic [1993-]': 'Czech Republic', 'Denmark': 'Denmark', 'Estonia [1992-]': 'Estonia', 'Finland': 'Finland',
        'France': 'France', 'Germany [FRG/Reunified]': 'Germany', 'Greece': 'Greece', 'Hungary': 'Hungary', 'Iceland': 'Iceland',
        'Italy': 'Italy', 'Latvia [1992-]': 'Latvia', 'Lithuania [1992-]': 'Lithuania', 'Montenegro [1992-]': 'Montenegro',
        'Netherlands': 'Netherlands', 'North Macedonia [1991-]': 'Macedonia', 'Norway': 'Norway', 'Poland': 'Poland',
        'Portugal': 'Portugal', 'Romania': 'Romania', 'Slovakia [1993-]': 'Slovakia', 'Slovenia': 'Slovenia', 'Spain': 'Spain',
        'Sweden': 'Sweden', 'Turkey': 'Turkey', 'United Kingdom': 'UK', 'NATO': 'NATO'}
HCC = {n: i for i, n in enumerate(BS['CountryName']) if n}


def CTRY(Pl):
    return HCC[CMAP[Pl['country']]]


def classkey(kind, n):
    if kind == 'air':
        return n.split('[')[0].strip()
    m = re.match(r'^(.*?)\s*\[(.*)\]\s*$', n)
    if m:
        pre, br = m.group(1), m.group(2)
        if re.match(r'^(Type|Pr\.|Project)\s', pre):
            return pre
        return re.sub(r'\s*Class\b', '', br).split(',')[0].strip()
    return re.sub(r'^(?:[A-Z]{1,5}\s?)?\d+\s+', '', n).strip()


def _toks(s):
    s = s.upper().replace('-', '').replace('/', ' ')
    return set(re.findall(r'[A-Z]*\d+[A-Z0-9]*|[A-Z]{3,}', s)) - {'TYPE', 'CLASS', 'BLK', 'BLOCK', 'MOD', 'UAV', 'UCAV'}


SUBTYPE_OF = {'CV': 'CV', 'CVN': 'CVN', 'CVH': 'CVH', 'CVL': 'CVL', 'DDH': 'DDG', 'CG': 'CG', 'CGN': 'CGN', 'BCGN': 'BCGN',
              'DDG': 'DDG', 'DD': 'DD', 'FFG': 'FFG', 'FF': 'FF', 'FFL': 'FFL', 'FS': 'FFL', 'LHA': 'LHA', 'LHD': 'LHD',
              'LPD': 'LPD', 'LSD': 'LSD', 'LST': 'LST', 'LPH': 'LPH', 'AOR': 'AOR', 'AOE': 'AOE', 'AO': 'AO', 'AFS': 'AFS',
              'LCC': 'LCC', 'PTG': 'PTG', 'PGG': 'PTG', 'PG': 'PG', 'SS': 'SS', 'SSK': 'SS', 'SSN': 'SSN', 'SSBN': 'SSBN',
              'SSGN': 'SSGN', 'SSG': 'SSG', 'SSP': 'SS'}
ACT = {'Fighter': 0, 'Bomber': 1, 'Attack': 2, 'Anti-Submarine': 3, 'Electronic': 4, 'Airborne Early': 5, 'Transport': 6,
       'Recon': 7, 'Maritime Patrol': 9, 'Tanker': 10, 'Multirole': 0, 'Unmanned Combat': 2, 'Area Surveillance': 7,
       'Airborne Command': 5}
_ANALOG_CACHE = {}


def pick_analog(Pl):
    key = (Pl['kind'], Pl['country'], Pl['key'])
    if key in _ANALOG_CACHE:
        return _ANALOG_CACHE[key]
    c = Pl['core']
    cc = str(CTRY(Pl))
    if Pl['kind'] in ('ship', 'sub'):
        annex = 'a1' if Pl['kind'] == 'ship' else 'a2'
        st = E['EnumShipType' if Pl['kind'] == 'ship' else 'EnumSubmarineType'].get(c['Type'], '').split(' -')[0].strip()
        want = SHIPTYPE_IDX.get(SUBTYPE_OF.get(st, st))
        disp = fnum(c['DisplacementStandard']) or fnum(c['DisplacementFull']) or 1000
        best, bd = None, 1e9
        for r in H[annex][1]:
            if r['classname'] == 'donotuse' or int(r['displacement'] or 0) <= 0 or r['mount_array'].startswith('0'):
                continue
            d = abs(math.log(max(1, int(r['displacement']))) - math.log(disp))
            if want is not None and r['subtype'] != str(want):
                d += 3
            if r['country'] != cc:
                d += 0.7
            d -= 0.4 * len(_toks(Pl['key']) & _toks(r['classname']))
            if d < bd:
                best, bd = r, d
    else:
        role = E['EnumAircraftType'].get(c['Type'], '')
        cat = E['EnumAircraftCategory'].get(c['Category'], '')
        want = next((v for k, v in ACT.items() if k in role), None)
        heli = 'Helicopter' in cat or 'Tiltrotor' in cat
        kt = _toks(Pl['key'])
        best, bd = None, 1e9
        for r in H['b1'][1]:
            if not r['Loadout_array'] or r['Loadout_array'] == '0':
                continue
            rh = r['type'] == '72'
            d = 0.0
            ov = kt & _toks(r['classname'])
            d -= 3 * len([x for x in ov if re.search(r'\d', x)]) + len([x for x in ov if not re.search(r'\d', x)])
            if heli != rh:
                d += 6
            if want is not None and r['subtype'] != str(want):
                d += 1.5
            if r['country'] != cc:
                d += 0.5
            if d < bd:
                best, bd = r, d
    _ANALOG_CACHE[key] = best
    ANALOG[Pl['kind'] + '|' + Pl['key']] = best['classname']
    return best


def hc_platform_name(Pl):
    n = Pl['key'].replace(' UAV', '').replace(' UCAV', '')
    n = re.sub(r'\s*\[(.*?)\]', r' \1', n).replace(',', ';')
    return f"{n} ({Pl['year']})"


def cmo_hull_names(Pl):
    tab = 'Ships' if Pl['kind'] == 'ship' else 'Submarines'
    names = []
    for r in D['flat'][tab].values():
        if r['Country'] != Pl['country'] or classkey(Pl['kind'], r['Name']) != Pl['key']:
            continue
        n = r['Name']
        m = re.match(r'^(.*?)\s*\[(.*)\]\s*$', n)
        if m and re.match(r'^(Type|Pr\.|Project)\s', m.group(1)):
            hull = m.group(2).split(',')[-1].strip()
        else:
            hull = m.group(1) if m else n
        hull = re.sub(r'^(?:[A-Z]{1,5}\s?)?(?:\d+\s+)', '', hull).strip()
        hull = re.sub(r'^(SKR|MPK|BDK|RKR|TAKR|VTR|BPK|EM|MRK|K|F|D|L|A|S|P)\s+', '', hull)
        if hull and not re.search(r'TBD|XXX', hull):
            names.append(hull)
    return list(dict.fromkeys(names))


def class_names(Pl, analog):
    out = cmo_hull_names(Pl)
    return out or [hc_platform_name(Pl).split(' (')[0]]




AIR_OV = [
 (r'CP-140', 'CP-140 Aurora'), (r'OP-3C|P-3B', 'P-3C Update III AIP'), (r'Z-9D', 'Z-9EC'), (r'MiG-35', 'MiG-29M Fulcrum E'),
 (r'F-16V|Blk 70|Blk 72', 'F-16CM Blk 50/52 (2022)'), (r'F-16CJ', 'F-16C/D Blk50/52'),
 (r'J-20|Su-57', 'F-22A Raptor (2021)'), (r'KF-21', 'F-15EX Eagle II (2023)'), (r'Kaan|TF-X', 'F-35A (2026)'),
 (r'Su-34', 'Su-34 Fullback'), (r'Su-30SM', 'Su-30SM Flanker'), (r'MiG-31', 'MiG-31BM Foxhound'),
 (r'Okhotnik|GJ-11|S-70 ', 'X-45C Phantom Ray'),
 (r'Bayraktar|Akinci|Aksungur|CH-4|CH-5|Wing Loong|BZK-005|Songar|TB-001|Anka|Forpost|Inokhodets', 'MQ-9A Reaper'),
 (r'J-10C|J-10A?H|J-10S', 'J-10B'), (r'J-11B', 'J-11B'), (r'J-15D|J-16D', 'EA-18G Growler (2025)'),
 (r'Poseidon MRA', 'P-8A Poseidon'), (r'Typhoon', 'Eurofighter Typhoon'), (r'Apache', 'AH-64E Guardian'),
 (r'FA-50', 'FA-50 Golden Eagle'), (r'Merlin|AW\.?101|EH\.?101', 'Merlin HM.1'), (r'LAH|Light Armed|T-129|T129', 'AH-1Z Viper'),
 (r'Tigre|Tiger', 'Tiger HAP'), (r'Z-20', 'MH-60R Seahawk'), (r'Ka-27|Ka-29', 'Ka-27PL Helix A'),
 (r'C-295|CN-295', 'CN-235MPA'), (r'Wildcat|AW\.?159', 'Wildcat HMA.1'), (r'A-50', 'A-50U Mainstay'),
 (r'Il-78', 'Il-78M Midas'), (r'KJ-', 'KJ-2000 Mainring'),
]
_pa_orig = pick_analog
def pick_analog(Pl):
    if Pl['kind'] == 'air':
        for rx, nm in AIR_OV:
            if re.search(rx, Pl['key'], re.I):
                cands = [r for r in H['b1'][1] if r['classname'].strip().strip('"').startswith(nm)
                         and r['Loadout_array'] and r['Loadout_array'] != '0']
                if cands:
                    ANALOG['air|' + Pl['key']] = cands[0]['classname']
                    return cands[0]
                print('AIR_OV miss', nm)
    return _pa_orig(Pl)

if __name__ == '__main__':
    import sys
    for k, Pl in P.items():
        if Pl['kind'] == 'ship':
            build_surface(Pl)
        elif Pl['kind'] == 'sub':
            build_sub(Pl)
    for k, Pl in P.items():
        if Pl['kind'] == 'air':
            build_aircraft(Pl)
    conform()
    out = {'NEW': NEW, 'MAGS': NEW_MAGS, 'NAMES': NEW_NAMES, 'STR': NEW_STR, 'LOG': LOG, 'KEYS': {'W': NEWW, 'S': NEWS}}
    json.dump(out, open('built2.json', 'w'), indent=0)
    print({k: len(v) for k, v in NEW.items()}, 'mags', len(NEW_MAGS), 'names', len(NEW_NAMES), 'strings', len(NEW_STR))
    print('alloc next', A.next)
