import cmo_lib as L, re, collections, json
D=L.load_cmo(); F=D['flat']
def yr(r):
    try: return int(float(r['YearIn']))
    except: return 0
EXCL_SHIPTYPE=re.compile(r'USV|UUV|ROV|SDV|Small Watercraft|Civilian|PB - |PC - |AGOR|T-AH|AGB|ATS|ATLS|LCM|Merchant|A - Auxiliary|T-AKR',re.I)
EXCL_AC=re.compile(r'Trainer|Commercial|Search And Rescue|Utility',re.I)
EXCL_ACNAME=re.compile(r'VC-25|VH-92|C-32|C-37|C-40|Gulfstream|T-6A|T-7A|T-54|TH-73|UH-72|Grob|TC-135|WC-135|Puma|ScanEagle|Altius|RQ-28|V-BAT|RQ-29|RQ-20|RQ-7B|Jet Ski|MC-12S|RC-12|U-28A|CN-235|EC-130SJ|SOLL|C-17A|C-130J|MC-130J|HC-130J|HC-27J|MH-47G|CH-47F|UH-60|MH-60M|SB-1|MV-75|MH-139|E-130J|E-6B|HC-144|E-3D|A-29C|AT-6E|F/A-18C\+|F/A-18D|KC-135R\(RT\)|KC-135T|RC-135[SUV]|MQ-1C Gray|Reaper ER|KC-130J',re.I)
EXCL_SHIPNAME=re.compile(r'T-HST|^LPD 17 San Antonio$',re.I)
def key(kind,n,t):
    if kind=='air':
        m=re.match(r'F-16CM? Blk (\d)(\d)',n)
        if m: 
            b=int(m.group(1)+m.group(2)); pair={30:'30/32',32:'30/32',40:'40/42',42:'40/42',50:'50/52',52:'50/52'}[b]
            return ('F-16CM' if b>=40 else 'F-16C')+' Blk '+pair
        return n
    nm=re.sub(r'^(?:T-)?[A-Z]{2,5}\s*\d+\s+','',n)
    b=re.search(r'\[(.*)\]',nm)
    cls=nm
    if b:
        inner=b.group(1); outer=nm[:b.start()].strip()
        if re.search(r'\bClass\b',inner):
            cls=re.sub(r'\s*Class\b','',inner).replace(',','')
        elif inner.startswith(('Flight','Blk','Los Angeles','Arleigh','Ticonderoga','Virginia','America','San Antonio','Whidbey','Montford','Spearhead')):
            cls=inner if not inner.startswith(('Flight','Blk')) else outer+' '+inner
        else: cls=nm
    return t.split(' -')[0]+' '+cls
def main():
    sel={}
    for kind,tab in [('ship','Ships'),('sub','Submarines'),('air','Aircraft')]:
        g=collections.defaultdict(list)
        for r in F[tab].values():
            if r['Country']!='United States' or not(2015<=yr(r)<=2031) or r['Hypothetical'] or r['Deprecated']: continue
            if kind=='ship' and (EXCL_SHIPTYPE.search(r['Type']) or EXCL_SHIPNAME.search(r['Name'])): continue
            if kind=='sub' and not re.match(r'SS',r['Type']): continue
            if kind=='air' and (EXCL_AC.search(r['Type']) or EXCL_ACNAME.search(r['Name'])): continue
            g[key(kind,r['Name'],r['Type'])].append(r)
        for k,rs in g.items():
            cur=[r for r in rs if yr(r)<=2026] or rs
            sel[(kind,k)]=max(cur,key=lambda r:(yr(r),int(r['ID'])))
    for (kind,k),r in sorted(sel.items()):
        print(f"{kind:4} | {k:45} | {r['ID']:5} {r['YearIn']} {r['Name']}")
    print(len(sel), collections.Counter(k[0] for k in sel))
    json.dump([{'kind':k[0],'key':k[1],'id':r['ID'],'year':yr(r),'name':r['Name']} for k,r in sorted(sel.items())],open('selection.json','w'),indent=1)
if __name__=='__main__':
    main()
