import json, os, shutil, cmo_lib as L
from unidecode import unidecode
def TL(x):
    if isinstance(x,str): return ''.join(c if ord(c)<256 else unidecode(c) for c in x)
    if isinstance(x,list): return [TL(i) for i in x]
    if isinstance(x,dict): return {k:TL(v) for k,v in x.items()}
    return x
B=TL(json.load(open('built2.json')))
SRC=os.path.expanduser('~/w/base2'); OUT=os.path.expanduser('~/w/out2/res')
os.makedirs(OUT,exist_ok=True)
def hdr(f):
    with open(f'{SRC}/{f}',encoding='latin-1',newline='') as fh: return [h.strip() for h in fh.readline().split(',')]
def fmt(h,row):
    vals=[]
    for c in h:
        v=str(row[c])
        vals.append('"'+v.replace('"',"'").replace(',',';')+'"' if c in('classname','name') else v)
    return ','.join(vals)

import collections as _C
_z={int(r['id']):r for r in B['NEW']['z1']}
_use=_C.Counter()
for k in ('a1','a2'):
    for r in B['NEW'][k]:
        for m in set(L.arr(r['mount_array'])): _use[m]+=1
_next=max(_z)+1
import copy
for k in ('a1','a2'):
    for r in B['NEW'][k]:
        a=L.arr(r['mount_array']); c=_C.Counter(a); out=[]; rep={}
        for m,n in c.items():
            if n>1 and m in _z:
                if _use[m]==1: nz=_z[m]
                else:
                    nz=copy.deepcopy(_z[m]); nz['id']=str(_next); _z[_next]=nz; B['NEW']['z1'].append(nz); _next+=1
                nz['nummounts']=str(int(nz['nummounts'])*n); rep[m]=int(nz['id'])
        for m in a:
            m2=rep.get(m,m)
            if m in rep and m2 in out: continue
            out.append(m2)
        if len(out)<len(a): print('collapsed',r['classname'],len(a),'->',len(out))
        r['mount_array']=L.mkarr(out[:32])
for zr in B['NEW']['z1']:
    n=int(zr['nummounts'])
    if n>9:
        f=next(f for f in range(2,n+1) if n%f==0 and n//f<=9)
        zr['nummounts']=str(n//f); zr['numroundsmnt']=str(int(zr['numroundsmnt'])*f)
        print('z1',zr['id'],n,'->',zr['nummounts'],'x',zr['numroundsmnt'])
for r in B['NEW']['b1']:
    a=L.arr(r['sensor_array'])
    if len(a)>3: r['sensor_array']=L.mkarr(a[:3])
for r in B['NEW']['d1']:
    for f in ('airph','surfph','subph','landph'):
        if f in r and int(r[f])>90: r[f]='90'
counts={}
LIM={'a1':25,'a2':24,'b1':23,'c1':26,'d1':27,'e1':25,'f1':19,'g1':25,'g2':23,'j1':27,'m1':29,'z1':29}
for k,rows in B['NEW'].items():
    for r in rows:
        if 'classname' in r: assert len(r['classname'])<=LIM[k], (k,r['classname'])
for k,rows in B['NEW'].items():
    f=f'annex_{k}.csv'
    if not rows: continue
    h=hdr(f)
    data=open(f'{SRC}/{f}','rb').read()
    assert data.endswith(b'\r\n')
    add=''.join(fmt(h,r)+'\r\n' for r in rows)
    open(f'{OUT}/{f}','wb').write(data+add.encode('latin-1'))
    counts[f]=len(rows)
def app(f,lines):
    data=open(f'{SRC}/{f}','rb').read(); assert data.endswith(b'\r\n')
    open(f'{OUT}/{f}','wb').write(data+''.join(l+'\r\n' for l in lines).encode('latin-1'))
    counts[f]=len(lines)
app('annex_mags.csv',[f'{i},{w},{c},{rt}' for i,w,c,rt in B['MAGS']])
app('annex_ship_names.csv',[f'{i},{sid},{len(n)}:'+':'.join('"'+x+'"' for x in n) for i,sid,n in B['NAMES']])
app('annex_strings.csv',[f'{i}, {t}' for i,t in B['STR']])
print(counts)
