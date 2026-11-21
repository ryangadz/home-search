"""Shared walkability scoring: places + walking-network distances -> a 0-100 score.

The recipe follows the published Walk Score method (nearest places per category,
weighted, with distance decay). It is our own estimate, not the official score.

Distances: the nearest place in each category is measured along the walking network
(streets, paths, sidewalks from OpenStreetMap). For categories that count several
places (restaurants, shops, coffee) the 2nd..nth nearest use straight-line distance
scaled by the local detour ratio found for the nearest one.
"""
import os, math
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'data', 'work')
MILE = 1609.344
WALK_M_PER_MIN = 80.0          # ~3 mph
LAT0, LON0 = 47.55, -122.20
MIN_DETOUR, MAX_DETOUR = 1.15, 6.0
DECAY_X = [0, .25, .5, .75, 1.0, 1.5]          # miles on foot
DECAY_Y = [1, 1, .65, .33, .10, 0]             # share of full credit (fitted against official scores, see check_points.py)
WEIGHTS = {
    'grocery': [3.0],
    'food':    [.75, .45, .25, .25, .225, .225, .225, .225, .2, .2],
    'shop':    [.5, .45, .4, .35, .3],
    'coffee':  [1.25, .75],
    'bank':    [1.0], 'park': [1.0], 'school': [1.0], 'books': [1.0], 'fun': [1.0],
}
TOTAL_W = sum(sum(v) for v in WEIGHTS.values())   # 15


def to_xy(lat, lon):
    return np.column_stack([(np.asarray(lon, float) - LON0) * math.cos(math.radians(LAT0)) * 111320.0,
                            (np.asarray(lat, float) - LAT0) * 110574.0])


def decay(miles):
    return np.interp(miles, DECAY_X, DECAY_Y)


class Walk:
    def __init__(self):
        self.pois = pd.read_csv(os.path.join(WORK, 'pois.csv'), dtype={'name': str, 'kind': str, 'cat': str})
        self.pois['name'] = self.pois['name'].fillna('')
        self.trees = {c: cKDTree(to_xy(*self.pois[self.pois.cat == c][['lat', 'lon']].values.T)) for c in WEIGHTS}
        self.food_tree = cKDTree(to_xy(*self.pois[self.pois.cat.isin(['food', 'coffee'])][['lat', 'lon']].values.T))
        f = np.load(os.path.join(WORK, 'walkfield.npz'))
        self.field = {k: f[k] for k in f.files}
        self.node_tree = cKDTree(to_xy(self.field['lat'], self.field['lon']))
        st = pd.read_csv(os.path.join(WORK, 'stations.csv'))
        self.stations = st[~st.name.str.contains('Gates|Garage', regex=True) & (st.lat > 47.30)].reset_index(drop=True)

    def snap(self, P):
        d, node = self.node_tree.query(P, k=1)
        return d, node

    def nearest_m(self, cat, snap_d, node):
        """Walking metres to the nearest place of a category (1e9 if out of reach)."""
        return snap_d + self.field['d_' + cat][node].astype(float)

    def score(self, P, parts=False):
        """P: (n,2) local metres -> walkability 0-100 (and optionally each category's share)."""
        snap_d, node = self.snap(P)
        total = np.zeros(len(P)); out = {}; detour = {}
        for cat, w in WEIGHTS.items():
            k = len(w)
            net1 = self.nearest_m(cat, snap_d, node)
            de, _ = self.trees[cat].query(P, k=k)
            de = de.reshape(len(P), -1)
            ratio = np.clip(net1 / np.maximum(de[:, 0], 40.0), MIN_DETOUR, MAX_DETOUR)
            dist = de * ratio[:, None]
            dist[:, 0] = net1
            dist = np.maximum(dist, net1[:, None])
            s = (decay(dist / MILE) * np.asarray(w)).sum(axis=1)
            total += s; out[cat] = s / sum(w); detour[cat] = ratio
        res = 100.0 * total / TOTAL_W
        return (res, out, detour, snap_d, node) if parts else res
