import csv, os, collections, cmo_lib as L
OUT=os.path.expanduser('~/w/out/res'); SRC=os.path.expanduser('~/w/hc/res')
def load(d,f):
    p=f'{d}/{f}' if os.path.exists(f'{d}/{f}') else f'{SRC}/{f}'
    with open(p,encoding='latin-1',newline='') as fh:
        r=csv.reader(fh,skipinitialspace=True); h=[x.strip() for x in next(r)]
        return h,[row for row in r if row]
T={}
for f in os.listdir(SRC):
    if f.endswith('.csv') and 'bs_' not in f and 'strings' not in f: T[f[6:-4]]=load(OUT,f)
# strings separately (commas inside)
S=[l.split(',',1)[0] for l in open(f'{OUT}/annex_strings.csv',encoding='latin-1',newline='').read().split('\r\n')[1:] if l]
errs=[]
ids={k:[int(r[0]) for r in rows] for k,(h,rows) in T.items()}
for k,v in ids.items():
    c=collections.Counter(v); d=[i for i,n in c.items() if n>1]
    if d: errs.append(f'dup ids {k} {d[:5]}')
sid=set(int(x) for x in S)
if len(sid)!=len(S): errs.append('dup string idx')
I={k:set(v) for k,v in ids.items()}
W=I['c1']|I['d1']|I['e1']|I['f1']|I['g1']|I['g2']
SEN=I['j1']|I['m1']
def col(k,c):
    h,rows=T[k]; i=h.index(c); return [(r[0],r[i]) for r in rows]
chk=[('a1','mount_array',I['z1']),('a1','sensor_array',SEN|I['g2']),('a1','mag_array',I['mags']),
     ('a2','mount_array',I['z1']),('a2','sensor_array',SEN),
     ('b1','sensor_array',SEN),('b1','Loadout_array',I['y1']),('p1','mount_array',I['z1']),('p1','sensor_array',SEN),('p1','mag_array',I['mags']),
     ('y1','weapon_array',W|SEN),('z2','weapon_array',W)]
for k,c,valid in chk:
    for i,s in col(k,c):
        a=L.arr(s)
        if int(s.split(':')[0])!=len(s.split(':'))-1: errs.append(f'bad array count {k} {i} {c} {s}')
        for v in a:
            if v not in valid: errs.append(f'{k} {i} {c} -> {v} missing')
for i,v in col('z1','wepid'):
    if int(v) not in W|I['z2']|{65535}: errs.append(f'z1 {i} wepid {v}')
for i,v in col('mags','Wepid'):
    if int(v) not in W: errs.append(f'mags {i} wep {v}')
for i,v in col('ship_names','ship_id'):
    if int(v) not in I['a1']|I['a2']: errs.append(f'names {i} -> {v}')
for k in ('a1','a2','b1'):
    for i,v in col(k,'textindex'):
        if int(v) not in sid: errs.append(f'{k} {i} text {v}')
# annex id range
for k,v in ids.items():
    if k in('mags','ship_names'): continue
    base=min(v)//4096*4096
    bad=[x for x in v if x//4096*4096!=base]
    if bad: errs.append(f'{k} ids outside annex block {bad[:5]}')
    if len(v)>4096: errs.append(f'{k} >4096 rows')
# field maxima: compare new rows vs original maxima
orig={k:load(SRC,f'annex_{k}.csv') for k in T}
for k,(h,rows) in T.items():
    oh,orows=orig[k]; n0=len(orows)
    for ci,c in enumerate(h):
        if c in('classname','name') or 'array' in c or c=='count:names': continue
        try: om=max(int(r[ci]) for r in orows); nm=max(int(r[ci]) for r in rows[n0:]) if rows[n0:] else None
        except ValueError: continue
        if nm is not None and nm>om: errs.append(f'{k}.{c}: new max {nm} > original max {om}')
    if 'classname' in h:
        ci=h.index('classname'); om=max(len(r[ci]) for r in orows)
        for r in rows[n0:]:
            if len(r[ci])>om: errs.append(f'{k} name too long {r[ci]} ({len(r[ci])}>{om})')
    for c in h:
        if 'array' in c:
            ci=h.index(c); om=max(int(r[ci].split(':')[0]) for r in orows)
            for r in rows[n0:]:
                if int(r[ci].split(':')[0])>om: errs.append(f'{k}.{c} array len {r[ci].split(":")[0]} > orig max {om} (id {r[0]})')
print(len(errs),'problems'); print('\n'.join(errs[:80]))
