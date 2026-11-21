"""Build the walking network (streets, paths, sidewalks) from an OpenStreetMap extract.

Usage: python3 scripts/02b_walk_network.py data/raw/washington-XXXXXX.osm.pbf
Writes data/work/walknet.npz: node lat/lon and edges (u, v, metres).
"""
import sys, os, math
from array import array
import numpy as np
import osmium

BBOX = (-122.52, 47.20, -121.82, 47.85)   # the mapped area plus a walking margin
WALK = {'residential', 'tertiary', 'secondary', 'primary', 'unclassified', 'living_street', 'service',
        'footway', 'path', 'pedestrian', 'steps', 'cycleway', 'track', 'road', 'corridor', 'bridleway',
        'tertiary_link', 'secondary_link', 'primary_link'}
FOOT_OK = {'yes', 'designated', 'permissive'}


def walkable(tags):
    h = tags.get('highway'); foot = tags.get('foot')
    if h in ('trunk', 'trunk_link'):
        if foot not in FOOT_OK and tags.get('sidewalk') not in ('both', 'left', 'right', 'yes'):
            return False
    elif h not in WALK:
        return False
    if foot in ('no', 'private', 'use_sidepath'):
        return False
    if tags.get('access') in ('private', 'no') and foot not in FOOT_OK:
        return False
    return True


def main():
    pbf = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work = os.path.join(root, 'data', 'work'); os.makedirs(work, exist_ok=True)
    idx = {}
    lat = array('f'); lon = array('f')
    eu = array('i'); ev = array('i'); el = array('f')
    k = math.cos(math.radians(47.55)) * 111320.0
    fp = osmium.FileProcessor(pbf).with_locations().with_filter(osmium.filter.KeyFilter('highway'))
    n_ways = 0
    for o in fp:
        if not o.is_way():
            continue
        nodes = o.nodes
        if len(nodes) < 2:
            continue
        first = nodes[0]
        if not first.location.valid():
            continue
        if not (BBOX[0] <= first.lon <= BBOX[2] and BBOX[1] <= first.lat <= BBOX[3]):
            continue
        if not walkable({t.k: t.v for t in o.tags}):
            continue
        n_ways += 1
        prev = None
        for n in nodes:
            if not n.location.valid():
                prev = None; continue
            i = idx.get(n.ref)
            if i is None:
                i = len(lat); idx[n.ref] = i
                lat.append(n.lat); lon.append(n.lon)
            if prev is not None and prev[0] != i:
                d = math.hypot((n.lon - prev[1]) * k, (n.lat - prev[2]) * 110574.0)
                eu.append(prev[0]); ev.append(i); el.append(d)
            prev = (i, n.lon, n.lat)
    out = os.path.join(work, 'walknet.npz')
    np.savez_compressed(out, lat=np.frombuffer(lat, dtype='f4'), lon=np.frombuffer(lon, dtype='f4'),
                        u=np.frombuffer(eu, dtype='i4'), v=np.frombuffer(ev, dtype='i4'), w=np.frombuffer(el, dtype='f4'))
    print('ways', n_ways, 'nodes', len(lat), 'edges', len(eu), '->', out)


if __name__ == '__main__':
    main()
