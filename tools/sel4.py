import cmo_lib as L, re, collections, json, os, sys
L.HC=os.path.expanduser('~/w/out3/res')
D=L.load_cmo(); H=L.load_hc(); F=D['flat']
HCC={n:i for i,n in enumerate(H['bs']['CountryName']) if n}
import countries as CN
_cs=set(r['Country'] for t in ['Ships','Submarines','Aircraft'] for r in F[t].values())
CM,_added=CN.build_map(L.HC,_cs)
CMAP=CM
def yr(r):
    try: return int(float(r['YearIn']))
    except: return 0
XT={'USV','Civilian','Merchant','Small Watercraft','LCU','LCM','LCAC','LCVP','LCP','LCPA','LCT','LCI','AGS','AGOR','AX','AGB','ASR','DSV','DTV','YRT','YAG','ATA','ATS','AGL','AH','T-AH','Platform','NGS Buoy','Mobile Offshore Base (MOB)','Special (Land Unit/Satellite)','LSDV','AGM','AP','AK','T-AK','AKR','T-AKR','AOT','AOL','AG','A','AR','AS','AD','GPV','MST','MM','AVT','AV','ATLS','AGF','DD','DE','BB','CA','CL','CLC','CLH','CVA','CVS','PT','MTB','PHT','APA','APD','AF','LSV','LSU','PB','WPB','AKS','MCD'}
class _X:
    def match(self,t): return t.split(' - ')[0].strip() in XT
SHIPX=_X()
SUBOK=re.compile(r'^SS')
ACX=re.compile(r'Trainer|Commercial|Civilian|Target|Aerostat|Blimp|Search And Rescue|Forward Observer|Laser|ASAT|Cargo$')
GEN={'type','class','mod','batch','flight','improved','the','pr','project','modified','new','upgrade','blk','block','mk','ii','iii','iv','i','v'}
def toks(s):
    s=s.lower().replace('pr.','pr ').replace('-','')
    t=set(re.findall(r'[a-z0-9]+',s))
    return {x for x in t if x not in GEN and (len(x)>=3 or x.isdigit() and len(x)>=2)}
def classkey(kind,n):
    if kind=='air': return n.split('[')[0].strip()
    m=re.match(r'^(.*?)\s*\[(.*)\]\s*$',n)
    if m:
        pre,br=m.group(1),m.group(2)
        if re.match(r'^(Type|Pr\.|Project)\s',pre) : return pre
        if re.match(r'^(Flight|Blk|Block|Batch|Baseline|Series)\b',br):
            return re.sub(r'^(?:[A-Z-]{1,6}\s?)?[\dX]+\s+','',pre).strip()+' '+br
        return re.sub(r'\s*Class\b','',br).split(',')[0].strip()
    return re.sub(r'^(?:[A-Z]{1,5}\s?)?\d+\s+','',n).strip()
done=set()
for f in ['selection.json','selection2.json','selection3.json']:
    for s in json.load(open(f)):
        done.add((s['kind'],s.get('country','United States'),s['key'])); done.add((s['kind'],s.get('country','United States'),classkey(s['kind'],s['name'])))
hcidx=collections.defaultdict(list)
for k in ['a1','a2','b1']:
    for r in H[k][1]: hcidx[(k,int(r['country']))].append((toks(r['classname']),r['classname']))
sel={}; skipped=collections.defaultdict(list)
for kind,tab,hk in [('ship','Ships','a1'),('sub','Submarines','a2'),('air','Aircraft','b1')]:
    g=collections.defaultdict(list)
    for r in F[tab].values():
        c=r['Country']
        if c not in CMAP or not(2015<=yr(r)<=2031) or r['Hypothetical'] or r['Deprecated']: continue
        if kind=='ship':
            if SHIPX.match(r['Type']): continue
            if float(r.get('Displacement_Full_t') or r.get('Displacement_Std_t') or 0)<150 and not r['Type'].startswith(('PCFG','PGM')): continue
        if kind=='sub' and not SUBOK.match(r['Type']): continue
        if kind=='air':
            if ACX.search(r['Type']): continue
            if 'UAV' in r['Type'] and 'Combat' not in r['Type'] and float(r['WeightMax_kg'] or 0)<1000: continue
            if re.search(r'Two-Seater|\bTrainer\b',r['Name']): continue
        g[(c,classkey(kind,r['Name']))].append(r)
    for (c,k),rs in g.items():
        if (kind,c,k) in done: continue
        cur=[r for r in rs if yr(r)<=2026] or rs
        best=max(cur,key=lambda r:(yr(r),int(r['ID'])))
        hcc=CM[c]; kt=toks(k); hit=None
        pool=hcidx.get((hk,hcc),[])+(hcidx.get((hk,HCC['CIS']),[]) if c.startswith('Russia') else [])
        for tk,nm in pool:
            if kt and (kt<=tk or (len(kt&tk)>=1 and any(re.search(r'\d',x) for x in kt&tk)) or (kind=='ship' and kt&tk and len(kt)==1)):
                hit=nm;break
        if not hit and kind!='air':
            lead=re.sub(r'^(?:[A-Z-]{1,6}\s?)?[\dX-]+\s+','',best['Name'].split('[')[0]).strip()
            lt={x for x in toks(lead) if not x.isdigit()}
            if lt:
                for tk,nm in pool:
                    if lt<=tk: hit=nm; break
        if hit and (kind,c,k) in {('ship','Australia','Cantabria')}: hit=None
        if hit: skipped[c].append((kind,k,hit)); continue
        sel[(kind,c,k)]=best
DROP=re.compile(r'Two-Seater|^F/A-18B|^F-16BM|^F-16DM|^F-16D |^F-16DG|^JAS 39D|^JAS 39F|^Rafale B|MiG-29KUB|MiG-35D|J-10SH|F-CK-1D|Airbus A\.319|Bombardier Global|Gulfstream G550 AEW|Falcon 7X|Challenger|C-32B|C-40A|King Air|P\.180|DHC-6|L-39NG|Hurjet|Hurkus|DA-42|Bell 505|Bell 429|MD-500|MD-530|H\.135|H145M|AW\.169|OH-58D|Il-96|Tu-214|VH-92|AT-6E|A-29C|Mi-171E$|Mi-171E2|Mi-17V7|Mi-171Sh|Z-20KA|Z-8B|Z-8L|Super King Air|Commercial|Hansa|C 110-4|L 110|MC-12S EMARSS-[GMV]',re.I)
sel={k:v for k,v in sel.items() if not DROP.search(k[2])}
out=[{'kind':k[0],'country':k[1],'key':k[2],'id':r['ID'],'year':yr(r),'name':r['Name'],'type':r['Type']} for k,r in sorted(sel.items())]
json.dump(out,open('selection4.json','w'),indent=0)
json.dump(skipped,open('skipped4.json','w'),indent=0)
print('selected',len(out),collections.Counter(s['kind'] for s in out))
byc=collections.defaultdict(collections.Counter)
for s in out: byc[s['country']][s['kind']]+=1
for c,d in sorted(byc.items(),key=lambda x:-sum(x[1].values())): print(f'{c[:24]:24}',dict(d))
print(collections.Counter(s['type'] for s in out).most_common(60))
