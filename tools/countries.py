import csv, re, os, collections
SKIPC = {'Junkyard', 'Commercial', 'Civilian', 'Terrorists', 'Generic', 'European Union [1993-]', 'Biologics', 'Unknown', 'Pirates'}
ALIAS = {'United States': 'USA', 'Soviet Union [-1991]': 'USSR', 'United Kingdom': 'UK', 'Russia [1992-]': 'Russia', 'Germany [FRG/Reunified]': 'Germany',
         'United Arab Emirates': 'UAE', 'Tajikistan': 'Tadjikistan', 'North Macedonia [1991-]': 'Macedonia',
         'Bosnia and Herzegovina': 'Bosnia', 'Bosnia-Herzegovina': 'Bosnia', 'Korea, North': 'North Korea', 'Korea, South': 'South Korea',
         'DRC/Zaire [1960-]': 'DR Congo', "Cote D'Ivoire [1960-]": 'Ivory Coast', 'Timor Leste [1975-]': 'East Timor',
         'Trinidad and Tobago [1962-]': 'Trinidad', 'Papua New Guinea': 'Papua New Guinea', 'Equatorial Guinea': 'Eq. Guinea',
         'Dominican Republic': 'Dominican Rep.'}
def _bs(path):
    for line in open(path, encoding='latin-1'):
        if line.startswith('"CountryName"'):
            return next(csv.reader([line]))
def hc_names(base):
    p = _bs(f'{base}/annex_bs_strings.csv')
    return p[3:]
def cmo_to_hc_name(c):
    if c in ALIAS: return ALIAS[c]
    return re.sub(r'\s*\[.*?\]', '', c).strip()
def build_map(base, cmo_countries, prev=()):
    """returns {cmo_country: hc_index}, list of (index,newname) appended"""
    names = hc_names(base)
    m, added = {}, []
    for i, n in prev:
        names[i] = n
    low = {n.lower(): i for i, n in enumerate(names) if n}
    nxt = max(i for i, n in enumerate(names) if n) + 1
    prevset = set(i for i, _ in prev)
    for c in sorted(cmo_countries):
        if c in SKIPC: continue
        n = cmo_to_hc_name(c)[:31]
        if n.lower() in low:
            m[c] = low[n.lower()]
            if m[c] in prevset and (m[c], n) not in added and all(a[0] != m[c] for a in added): added.append((m[c], names[m[c]]))
        else:
            low[n.lower()] = nxt; m[c] = nxt; added.append((nxt, n)); nxt += 1
    for i, n in prev:
        if all(a[0] != i for a in added): added.append((i, n))
    return m, added
def write_bs(src, dst, added):
    lines = open(src, encoding='latin-1', newline='').read().split('\r\n')
    for i, l in enumerate(lines):
        if l.startswith('"CountryName"'):
            p = next(csv.reader([l])); vals = p[3:]
            for idx, n in added: vals[idx] = n
            # rebuild in same quoting style
            lines[i] = '"CountryName",' + p[1] + ',' + p[2] + ',' + ','.join('"' + v + '"' for v in vals)
    open(dst, 'w', encoding='latin-1', newline='').write('\r\n'.join(lines))
