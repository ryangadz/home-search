"""Walking distance from every street/path node to the nearest place of each kind.

Usage: python3 scripts/02c_walk_field.py
Reads  data/work/walknet.npz, pois.csv, stations.csv
Writes data/work/walkfield.npz: node lat/lon, one distance array per category (metres
along the walking network, capped), plus distance to and index of the nearest Link station.
"""
import os, math
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'data', 'work')
CATS = ['grocery', 'food', 'shop', 'coffee', 'bank', 'park', 'school', 'books', 'fun']
LIMIT = 2600.0            # metres: a bit past the 1.5 mile cut-off of the score
RAIL_LIMIT = 8000.0
MIN_COMPONENT = 200
LAT0, LON0 = 47.55, -122.20


def to_xy(lat, lon):
    return np.column_stack([(np.asarray(lon, float) - LON0) * math.cos(math.radians(LAT0)) * 111320.0,
                            (np.asarray(lat, float) - LAT0) * 110574.0])


net = np.load(os.path.join(WORK, 'walknet.npz'))
n = len(net['lat'])
G = csr_matrix((net['w'].astype('f8'), (net['u'], net['v'])), shape=(n, n))
G = G.maximum(G.T)
ncomp, lab = connected_components(G, directed=False)
sizes = np.bincount(lab)
keep = sizes[lab] >= MIN_COMPONENT
print('nodes', n, 'components', ncomp, 'kept nodes', int(keep.sum()))
ids = np.flatnonzero(keep)
G = G[ids][:, ids].tocsr()
lat = net['lat'][ids]; lon = net['lon'][ids]
tree = cKDTree(to_xy(lat, lon))

pois = pd.read_csv(os.path.join(WORK, 'pois.csv'))
out = {'lat': lat.astype('f4'), 'lon': lon.astype('f4')}
for cat in CATS:
    sub = pois[pois.cat == cat]
    _, node = tree.query(to_xy(sub.lat.values, sub.lon.values), k=1)
    src = np.unique(node)
    d = dijkstra(G, directed=False, indices=src, min_only=True, limit=LIMIT)
    out['d_' + cat] = np.where(np.isfinite(d), d, 1e9).astype('f4')
    print(f'{cat:8s} sources {len(src):6d}  nodes within reach {int(np.isfinite(d).sum())}')

st = pd.read_csv(os.path.join(WORK, 'stations.csv'))
st = st[~st.name.str.contains('Gates|Garage', regex=True) & (st.lat > 47.30)].reset_index(drop=True)
_, snode = tree.query(to_xy(st.lat.values, st.lon.values), k=1)
d, _, source = dijkstra(G, directed=False, indices=snode, min_only=True, limit=RAIL_LIMIT, return_predecessors=True)
node_to_station = {int(nd): i for i, nd in enumerate(snode)}
out['d_rail'] = np.where(np.isfinite(d), d, 1e9).astype('f4')
out['rail_ix'] = np.array([node_to_station.get(int(s), -1) if s >= 0 else -1 for s in source], dtype='i2')
np.savez_compressed(os.path.join(WORK, 'walkfield.npz'), **out)
print('wrote walkfield.npz', round(os.path.getsize(os.path.join(WORK, 'walkfield.npz')) / 1e6, 1), 'MB')
