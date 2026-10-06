import cmo_lib as L, json, collections
D=L.load_cmo()
sel=json.load(open('selection2.json'))
W=D['Weapon']; S=D['Sensor']; R=D['WeaponRecord']
def rec(rid):
    r=R[rid]; return {'rec':rid,'wid':r['ComponentID'],'wname':W[r['ComponentID']]['Name'],'load':int(r['DefaultLoad']),'max':int(r['MaxLoad'])}
ARCS=['SB1','SB2','SMF1','SMF2','SMA1','SMA2','SS1','SS2','PB1','PB2','PMF1','PMF2','PMA1','PMA2','PS1','PS2']
def plat(kind,pid):
    pre={'ship':'Ship','sub':'Submarine','air':'Aircraft'}[kind]
    P={'kind':kind,'id':pid,'core':D[pre][pid]}
    mounts=[]
    for m in D.get(pre+'Mounts',{}).get(pid,[]):
        M=D['Mount'][m['ComponentID']]
        mounts.append({'mid':m['ComponentID'],'name':M['Name'],'arcs':[a for a in ARCS if m.get(a)=='1'],
            'rof':M['ROF'],'cap':M['Capacity'],'armor':M['ArmorGeneral'],'auto':M['Autonomous'],
            'weapons':[rec(w['ComponentID']) for w in D['MountWeapons'].get(m['ComponentID'],[])],
            'sensors':[w['ComponentID'] for w in D['MountSensors'].get(m['ComponentID'],[])]})
    P['mounts']=mounts
    mags=[]
    for m in D.get(pre+'Magazines',{}).get(pid,[]):
        M=D['Magazine'][m['ComponentID']]
        mags.append({'magid':m['ComponentID'],'name':M['Name'],'cap':M['Capacity'],'aviation':M['AviationMagazine'],
          'weapons':[rec(w['ComponentID']) for w in D['MagazineWeapons'].get(m['ComponentID'],[])]})
    P['mags']=mags
    P['sensors']=[s['ComponentID'] for s in D.get(pre+'Sensors',{}).get(pid,[])]
    P['codes']=[c['CodeID'] for c in D.get(pre+'Codes',{}).get(pid,[])]
    P['sig']=D.get(pre+'Signatures',{}).get(pid,[])
    P['prop']=[]
    for p in D.get(pre+'Propulsion',{}).get(pid,[]):
        pr=D['Propulsion'][p['ComponentID']]
        P['prop'].append({'name':pr['Name'],'type':pr['Type'],'perf':D['PropulsionPerformance'].get(p['ComponentID'],[])})
    if kind=='ship':
        P['facilities']=[D['Facility'].get(f['ComponentID'],{}) for f in D['ShipAircraftFacilities'].get(pid,[])]
    if kind=='air':
        lo=[]
        for l in D['AircraftLoadouts'].get(pid,[]):
            LO=D['Loadout'][l['ComponentID']]
            lo.append({'lid':l['ComponentID'],'name':LO['Name'],'role':LO['LoadoutRole'],'radius':LO['DefaultCombatRadius'],
               'ready':LO['ReadyTime'],'weapons':[rec(w['ComponentID']) for w in D['LoadoutWeapons'].get(l['ComponentID'],[])]})
        P['loadouts']=lo
        P['fuel']=D['AircraftFuel'].get(pid,[])
    return P
out={}
for s in sel:
    out[s['kind']+'|'+s['country']+'|'+s['key']]=dict(plat(s['kind'],s['id']),year=s['year'],cmoname=s['name'],key=s['key'],country=s['country'])
json.dump(out,open('platforms2.json','w'))
# summarize referenced weapons & sensors
wu=collections.Counter(); su=collections.Counter()
for P in out.values():
    for m in P['mounts']:
        for w in m['weapons']: wu[w['wid']]+=1
        for s in m['sensors']: su[s]+=1
    for m in P['mags']:
        for w in m['weapons']: wu[w['wid']]+=1
    for s in P['sensors']: su[s]+=1
    for l in P.get('loadouts',[]):
        for w in l['weapons']: wu[w['wid']]+=1
print('weapons',len(wu),'sensors',len(su))
print('loadouts total',sum(len(P.get('loadouts',[])) for P in out.values()))
json.dump({'weapons':list(wu),'sensors':list(su)},open('used2.json','w'))
