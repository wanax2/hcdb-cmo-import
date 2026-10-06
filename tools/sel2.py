import cmo_lib as L, re, collections, json
D=L.load_cmo(); H=L.load_hc(); F=D['flat']
HCC={n:i for i,n in enumerate(H['bs']['CountryName']) if n}
CMAP={'China':'China','Russia [1992-]':'Russia','North Korea':'North Korea','South Korea':'South Korea','Japan':'Japan',
 'Albania':'Albania','Belgium':'Belgium','Bulgaria':'Bulgaria','Canada':'Canada','Croatia [1992-]':'Croatia','Czech Republic [1993-]':'Czech Republic',
 'Denmark':'Denmark','Estonia [1992-]':'Estonia','Finland':'Finland','France':'France','Germany [FRG/Reunified]':'Germany','Greece':'Greece',
 'Hungary':'Hungary','Iceland':'Iceland','Italy':'Italy','Latvia [1992-]':'Latvia','Lithuania [1992-]':'Lithuania','Montenegro [1992-]':'Montenegro',
 'Netherlands':'Netherlands','North Macedonia [1991-]':'Macedonia','Norway':'Norway','Poland':'Poland','Portugal':'Portugal','Romania':'Romania',
 'Slovakia [1993-]':'Slovakia','Slovenia':'Slovenia','Spain':'Spain','Sweden':'Sweden','Turkey':'Turkey','United Kingdom':'UK','NATO':'NATO'}
def yr(r):
    try: return int(float(r['YearIn']))
    except: return 0
SHIPOK=re.compile(r'^(CVN?|CVH|CVL|DDH|CGN?|BCGN|DDG?|FFG?|FFL|FS|LHA|LHD|LPD|LSD|LST|LPH|AOR|AOE|AO|AFS|LCC|PTG|PGG|PG|CG) -')
ACOK=re.compile(r'Fighter|Multirole|Attack|Bomber|Airborne Early|Maritime Patrol|Anti-Submarine|Electronic|Tanker|Recon|Area Surveillance|Unmanned Combat|Airborne Command')
GEN={'type','class','mod','batch','flight','improved','the','pr','project','modified','new','upgrade','blk','block','mk','ii','iii','iv','i','v'}
def toks(s):
    s=s.lower().replace('pr.','pr').replace('-','')
    t=set(re.findall(r'[a-z0-9]+',s))
    return {x for x in t if x not in GEN and (len(x)>=3 or x.isdigit() and len(x)>=2)}
def classkey(kind,n):
    if kind=='air': return n.split('[')[0].strip()
    m=re.match(r'^(.*?)\s*\[(.*)\]\s*$',n)
    if m:
        pre,br=m.group(1),m.group(2)
        if re.match(r'^(Type|Pr\.|Project)\s',pre) : return pre
        br=re.sub(r'\s*Class\b','',br).split(',')[0].strip()
        return br
    return re.sub(r'^(?:[A-Z]{1,5}\s?)?\d+\s+','',n).strip()
hcidx=collections.defaultdict(list)
for k in ['a1','a2','b1']:
    for r in H[k][1]: hcidx[(k,int(r['country']))].append((toks(r['classname']),r['classname']))
sel={}; skipped=collections.defaultdict(list)
for kind,tab,hk in [('ship','Ships','a1'),('sub','Submarines','a2'),('air','Aircraft','b1')]:
    g=collections.defaultdict(list)
    for r in F[tab].values():
        c=r['Country']
        if c not in CMAP or not(2015<=yr(r)<=2031) or r['Hypothetical'] or r['Deprecated']: continue
        if kind=='ship' and not SHIPOK.match(r['Type']): continue
        if kind=='sub' and not re.match(r'SS',r['Type']): continue
        if kind=='air':
            if not ACOK.search(r['Type']): continue
            if 'UAV' in r['Type'] and 'Combat' not in r['Type'] and float(r['WeightMax_kg'] or 0)<5000: continue
        g[(c,classkey(kind,r['Name']))].append(r)
    for (c,k),rs in g.items():
        cur=[r for r in rs if yr(r)<=2026] or rs
        best=max(cur,key=lambda r:(yr(r),int(r['ID'])))
        hcc=HCC.get(CMAP[c])
        kt=toks(k)
        hit=None
        for tk,nm in hcidx.get((hk,hcc),[])+hcidx.get((hk,HCC['CIS']),[]) if c.startswith('Russia') else hcidx.get((hk,hcc),[]):
            if kt and (kt<=tk or (len(kt&tk)>=1 and any(x.isdigit() or re.search(r'\d',x) for x in kt&tk)) or (kind=='ship' and kt&tk and len(kt)==1)):
                hit=nm;break
        if hit: skipped[c].append((kind,k,hit)); continue
        sel[(kind,c,k)]=best
cnt=collections.Counter((c,kind) for kind,c,k in sel)
tot=collections.Counter(kind for kind,c,k in sel)
print('selected',len(sel),tot)
byc=collections.defaultdict(dict)
for (c,kind),n in cnt.items(): byc[c][kind]=n
for c,d in sorted(byc.items(),key=lambda x:-sum(x[1].values())): print(f'{c[:24]:24}',d)
json.dump([{'kind':k[0],'country':k[1],'key':k[2],'id':r['ID'],'year':yr(r),'name':r['Name']} for k,r in sorted(sel.items())],open('selection2.json','w'),indent=0)
json.dump({c:v for c,v in skipped.items()},open('skipped2.json','w'),indent=0)

# ---- post-filter & force-adds
import re as _re
DROP=_re.compile(r'Two-Seater|^F/A-18B|^F-16BM|^F-16DM|^F-16DJ|^JAS 39D|^JAS 39F|^Rafale B|MiG-29KUB|MiG-35D|J-10SH|Airbus A\.319|Bombardier Global|King Air|DHC-6|L-39NG|Hurjet|Hurkus|DA-42|Searcher|Shahed|VPU|Mi-8-MTPR|OH-58D|MD-530F|Mi-171|Il-96|^Batch I$|Y-9G|Y-9XZ|Y-9LG|Z-9C|Z-9D$|Z-8GZ',_re.I)
final=[s for s in json.load(open('selection2.json')) if not DROP.search(s['key'])]
force=[('sub','China','Type 041 Zhou'),('ship','South Korea','Incheon Batch II'),('ship','South Korea','Incheon Batch III'),('ship','South Korea','KDX-3 Batch 2'),('air','United Kingdom','Apache AH.Mk.2')]
tabs={'ship':'Ships','sub':'Submarines','air':'Aircraft'}
for kind,c,k in force:
    rs=[r for r in F[tabs[kind]].values() if r['Country']==c and classkey(kind,r['Name'])==k and 2015<=yr(r)<=2031 and not r['Hypothetical']]
    if rs:
        cur=[r for r in rs if yr(r)<=2026] or rs; b=max(cur,key=lambda r:(yr(r),int(r['ID'])))
        final.append({'kind':kind,'country':c,'key':k,'id':b['ID'],'year':yr(b),'name':b['Name']})
    else: print('force not found',k)
json.dump(final,open('selection2.json','w'),indent=0)
print('final',len(final),collections.Counter(s['kind'] for s in final))
