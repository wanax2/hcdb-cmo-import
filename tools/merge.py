import json, os, shutil, cmo_lib as L
B=json.load(open('built.json'))
SRC=os.path.expanduser('~/w/hc/res'); OUT=os.path.expanduser('~/w/out/res')
os.makedirs(OUT,exist_ok=True)
def hdr(f):
    with open(f'{SRC}/{f}',encoding='latin-1',newline='') as fh: return [h.strip() for h in fh.readline().split(',')]
def fmt(h,row):
    vals=[]
    for c in h:
        v=str(row[c])
        vals.append('"'+v.replace('"',"'").replace(',',';')+'"' if c in('classname','name') else v)
    return ','.join(vals)
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
