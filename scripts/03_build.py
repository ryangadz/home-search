"""Build the map's data files from King County records + OpenStreetMap.

Usage: python3 scripts/03_build.py
Reads  data/raw/EXTR_ResBldg.csv, EXTR_Accessory_V.csv, EXTR_Parcel.csv,
       data/raw/kc_parcel_address_slim.csv, and data/work/ (pois, stations, walkfield)
Writes web/data/homes.js, grid.js, places.js, meta.js
"""
import os, glob, json, math, base64, datetime
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
import walklib as wl

ROOT = wl.ROOT
RAW = os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, 'web', 'data')
os.makedirs(OUT, exist_ok=True)

MIN_SPACE = 600          # sq ft of garage + shop space for a house to be on the map
# Walkability layer extent and cell size
G_WEST, G_EAST, G_SOUTH, G_NORTH = -122.46, -121.88, 47.25, 47.80
G_CELL = 150.0           # Web-Mercator metres (~100 m on the ground at this latitude)
TEN_MIN = 10 * wl.WALK_M_PER_MIN


def num(s):
    return pd.to_numeric(s, errors='coerce').fillna(0)


def minutes(m, cap=99):
    return np.minimum(np.round(m / wl.WALK_M_PER_MIN), cap).astype(int)


W = wl.Walk()

# ---------------------------------------------------------------- county records
print('reading county records...')
rb = pd.read_csv(os.path.join(RAW, 'EXTR_ResBldg.csv'), encoding='latin-1', low_memory=False,
                 dtype={'Major': str, 'Minor': str},
                 usecols=['Major', 'Minor', 'NbrLivingUnits', 'Stories', 'BldgGrade', 'SqFtTotLiving',
                          'SqFtTotBasement', 'SqFtGarageBasement', 'SqFtGarageAttached', 'DaylightBasement',
                          'Bedrooms', 'BathFullCount', 'Bath3qtrCount', 'BathHalfCount', 'YrBuilt', 'Address'])
rb['PIN'] = rb.Major.str.zfill(6) + rb.Minor.str.zfill(4)
for c in ['SqFtTotLiving', 'SqFtTotBasement', 'SqFtGarageBasement', 'SqFtGarageAttached', 'Bedrooms',
          'BathFullCount', 'Bath3qtrCount', 'BathHalfCount', 'YrBuilt', 'NbrLivingUnits', 'BldgGrade']:
    rb[c] = num(rb[c])
rb = rb.sort_values('SqFtTotLiving', ascending=False)
grp = rb.groupby('PIN', sort=False)
res = grp.first()                                  # the main (largest) building's attributes
res['ga'] = grp.SqFtGarageAttached.sum()
res['gb'] = grp.SqFtGarageBasement.sum()
res['units'] = grp.NbrLivingUnits.sum()
n_houses = len(res)

acc = pd.read_csv(os.path.join(RAW, 'EXTR_Accessory_V.csv'), encoding='latin-1', dtype=str)
acc['PIN'] = acc.Major.str.zfill(6) + acc.Minor.str.zfill(4)
acc['t'] = acc.AccyType.str.strip()                # 1 = detached garage, 2 = carport, 8 = misc improvement
acc['size'] = num(acc.Size)
acc['desc'] = acc.AccyDescr.fillna('').str.strip()
ok = (acc['size'] >= 80) & (acc['size'] <= 20000)
det = acc[(acc.t == '1') & ok].groupby('PIN')['size'].sum().rename('gd')
carport = acc[(acc.t == '2') & ok].groupby('PIN')['size'].sum().rename('cp')
KW = r'\b(?:SHOP|WORKSHOP|BARN|POLE|HANGAR|RV)\b'
is_shop = (acc.t == '8') & ok & acc.desc.str.upper().str.contains(KW, regex=True)
shop = acc[is_shop].groupby('PIN')['size'].sum().rename('sh')
noted = acc[acc.t.isin(['1', '8']) & acc.desc.str.upper().str.contains(KW + r'|\bADU\b|\bSTUDIO\b', regex=True)]
notes = noted.groupby('PIN')['desc'].agg(lambda s: '; '.join(dict.fromkeys(x for x in s if x))[:90]).rename('note')

par = pd.read_csv(os.path.join(RAW, 'EXTR_Parcel.csv'), encoding='latin-1', dtype=str,
                  usecols=['Major', 'Minor', 'SqFtLot', 'TrafficNoise'])
par['PIN'] = par.Major.str.zfill(6) + par.Minor.str.zfill(4)
par = par.drop_duplicates('PIN').set_index('PIN')

addr = pd.read_csv(os.path.join(RAW, 'kc_parcel_address_slim.csv'), dtype=str)
addr['LAT'] = pd.to_numeric(addr.LAT, errors='coerce'); addr['LON'] = pd.to_numeric(addr.LON, errors='coerce')
addr = addr[(addr.LAT > 46.9) & (addr.LAT < 48.0) & (addr.LON < -121.0) & (addr.LON > -122.7)]
land_tree = cKDTree(wl.to_xy(addr.LAT.values, addr.LON.values))     # every addressed parcel: the land mask
addr = addr.drop_duplicates('PIN').set_index('PIN')

df = res.join(addr, how='inner').join(par[['SqFtLot', 'TrafficNoise']]).join(det).join(carport).join(shop).join(notes)
for c in ['gd', 'cp', 'sh']:
    df[c] = df[c].fillna(0)
df['note'] = df['note'].fillna('')
df['g'] = df.ga + df.gb + df.gd
n_located = len(df)
stats = {str(t): int((df.g >= t).sum()) for t in (600, 900, 1200, 1500)}
cand = df[(df.g + df.sh) >= MIN_SPACE]
cand = cand[(cand.LON >= G_WEST) & (cand.LON <= G_EAST) & (cand.LAT >= G_SOUTH) & (cand.LAT <= G_NORTH)].copy()
print('houses', n_houses, 'located', n_located, 'on the map', len(cand))

# ---------------------------------------------------------------- score the houses
P = wl.to_xy(cand.LAT.values, cand.LON.values)
score, parts, detour, snap_d, node = W.score(P, parts=True)
cand['walk'] = np.round(score).astype(int)
cand['groc'] = minutes(W.nearest_m('grocery', snap_d, node))
cand['park'] = minutes(W.nearest_m('park', snap_d, node))
cand['food'] = W.food_tree.query_ball_point(P, TEN_MIN / detour['food'], return_length=True)
cand['shops'] = W.trees['shop'].query_ball_point(P, TEN_MIN / detour['shop'], return_length=True)
cand['link'] = minutes(snap_d + W.field['d_rail'][node].astype(float))
cand['linkn'] = W.field['rail_ix'][node].astype(int)


def city_name(cty, postal):
    c = cty if isinstance(cty, str) and cty else 'King County'
    if c == 'King County' and isinstance(postal, str) and postal:
        return postal.title() + ' (uninc.)'
    return c


cand['city'] = [city_name(a, b) for a, b in zip(cand.CTYNAME, cand.POSTALCTYNAME)]
cities = sorted(cand.city.unique()); city_ix = {c: i for i, c in enumerate(cities)}
cand['use'] = cand.PREUSE_DESC.fillna('').astype(str).str.strip()
cand['zone'] = cand.KCA_ZONING.fillna('').astype(str).str.strip()
uses = sorted(cand.use.unique()); use_ix = {c: i for i, c in enumerate(uses)}
zones = sorted(cand.zone.unique()); zone_ix = {c: i for i, c in enumerate(zones)}
cand = cand.sort_values(['walk', 'g'], ascending=[False, False])

val_k = np.round((num(cand.APPRLNDVAL) + num(cand.APPR_IMPR)) / 1000).astype(int)
lot = num(cand.SqFtLot).astype(int).values
lot = np.where(lot > 0, lot, num(cand.LOTSQFT).astype(int).values)
baths = cand.BathFullCount + 0.75 * cand.Bath3qtrCount + 0.5 * cand.BathHalfCount
a1 = cand.ADDR_FULL.fillna('')
addr_txt = a1.where(a1 != '', cand.Address.fillna('').str.split().str.join(' '))
ints = lambda s: [int(v) for v in s]
homes = {
    'lat': [round(float(v), 5) for v in cand.LAT], 'lon': [round(float(v), 5) for v in cand.LON],
    'g': ints(cand.g), 'ga': ints(cand.ga), 'gb': ints(cand.gb), 'gd': ints(cand.gd), 'sh': ints(cand.sh), 'cp': ints(cand.cp),
    'liv': ints(cand.SqFtTotLiving), 'bsmt': ints(cand.SqFtTotBasement),
    'dayb': ints(cand.DaylightBasement.fillna('').astype(str).str.strip().str.upper() == 'Y'),
    'lot': ints(lot), 'yr': ints(cand.YrBuilt), 'bed': ints(cand.Bedrooms),
    'bath': [round(float(v), 2) for v in baths], 'units': ints(cand.units),
    'val': ints(val_k), 'walk': ints(cand.walk), 'groc': ints(cand.groc), 'park': ints(cand.park),
    'food': ints(cand.food), 'shops': ints(cand.shops), 'link': ints(cand.link), 'linkn': ints(cand.linkn),
    'noise': ints(num(cand.TrafficNoise)),
    'city': [city_ix[c] for c in cand.city], 'zip': cand.ZIP5.fillna('').tolist(),
    'use': [use_ix[c] for c in cand.use], 'zone': [zone_ix[c] for c in cand.zone],
    'addr': addr_txt.tolist(), 'pin': cand.index.tolist(), 'note': cand.note.tolist(),
}

# ---------------------------------------------------------------- walkability grid
def merc_x(lon): return math.radians(lon) * 6378137.0
def merc_y(lat): return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * 6378137.0
x0, x1, y0, y1 = merc_x(G_WEST), merc_x(G_EAST), merc_y(G_SOUTH), merc_y(G_NORTH)
gw = int(round((x1 - x0) / G_CELL)); gh = int(round((y1 - y0) / G_CELL))
mx = x0 + (np.arange(gw) + .5) * (x1 - x0) / gw
my = y1 - (np.arange(gh) + .5) * (y1 - y0) / gh           # row 0 = north
glon = np.degrees(mx / 6378137.0)
glat = np.degrees(2 * np.arctan(np.exp(my / 6378137.0)) - math.pi / 2)
LON, LAT = np.meshgrid(glon, glat)
GP = wl.to_xy(LAT.ravel(), LON.ravel())
gscore = np.round(W.score(GP)).astype(np.uint8)
dland, _ = land_tree.query(GP, k=1, distance_upper_bound=230)
gscore[~np.isfinite(dland)] = 255                           # water / nothing addressed nearby -> no data
grid = {'w': gw, 'h': gh, 'west': G_WEST, 'east': G_EAST, 'south': G_SOUTH, 'north': G_NORTH,
        'data': base64.b64encode(gscore.tobytes()).decode('ascii')}

# ---------------------------------------------------------------- places for the map
CATS = ['grocery', 'food', 'coffee', 'shop', 'bank', 'park_c', 'school', 'books', 'fun']
pois = W.pois
pm = pois[pois.cat.isin(CATS) & (pois.lon >= G_WEST) & (pois.lon <= G_EAST) & (pois.lat >= G_SOUTH) & (pois.lat <= G_NORTH)]
places = [[round(r.lat, 5), round(r.lon, 5), CATS.index(r.cat), r.name] for r in pm.itertuples()]

pbf = sorted(glob.glob(os.path.join(RAW, '*.osm.pbf')))
osm_date = ''
if pbf:
    stem = os.path.basename(pbf[-1]).split('-')[-1][:6]
    if stem.isdigit():
        osm_date = f'20{stem[:2]}-{stem[2:4]}-{stem[4:6]}'
assessor_date = datetime.date.fromtimestamp(os.path.getmtime(os.path.join(RAW, 'EXTR_ResBldg.csv'))).isoformat()
meta = {
    'built': datetime.date.today().isoformat(), 'min_space': MIN_SPACE,
    'n_houses': int(n_houses), 'n_located': int(n_located), 'n_map': int(len(cand)),
    'garage_counts': stats, 'cities': cities, 'uses': uses, 'zones': zones,
    'stations': [[round(r.lat, 5), round(r.lon, 5), r.name] for r in W.stations.itertuples()],
    'place_cats': ['Grocery', 'Restaurant or bar', 'Coffee or bakery', 'Shop', 'Bank', 'Park', 'School',
                   'Library or bookshop', 'Arts and entertainment'],
    'sources': {'assessor': 'extract of ' + assessor_date, 'osm': 'as of ' + osm_date if osm_date else ''},
}


def write_js(name, var, obj):
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('window.' + var + '=')
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
        f.write(';\n')
    print('wrote', name, round(os.path.getsize(path) / 1e6, 2), 'MB')


write_js('homes.js', 'HS_HOMES', homes)
write_js('grid.js', 'HS_GRID', grid)
write_js('places.js', 'HS_PLACES', places)
write_js('meta.js', 'HS_META', meta)

# ---------------------------------------------------------------- summary
print('\ngarage sq ft, all located houses:', stats)
print('garage >=   walk>=50  walk>=70  walk>=80  walk>=90')
for g in (600, 900, 1200, 1500):
    row = [int(((cand.g >= g) & (cand.walk >= w)).sum()) for w in (50, 70, 80, 90)]
    print(f'{g:9d}  ' + '  '.join(f'{v:8d}' for v in row))
top = cand[(cand.g >= 1200) & (cand.walk >= 70)].groupby('city').size().sort_values(ascending=False).head(12)
print('\nwhere the 1,200+ sq ft garages with walkability 70+ are:\n' + top.to_string())
