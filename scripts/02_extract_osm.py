"""Pull walkability-relevant places out of an OpenStreetMap extract.

Usage: python3 scripts/02_extract_osm.py data/raw/washington-XXXXXX.osm.pbf
Writes data/work/pois.csv (lat, lon, cat, name, kind) and data/work/stations.csv.

Categories follow the published Walk Score recipe: grocery, food, coffee, shop,
bank, park, school, books, fun. Parks are written as points along their boundary
(every ~60 m) so "distance to the park" means distance to its edge, not its middle.
"""
import sys, os, csv, math
import osmium

BBOX = (-122.62, 47.00, -121.55, 47.86)   # lon0, lat0, lon1, lat1: King County + margin

GROCERY = {'supermarket', 'greengrocer', 'grocery', 'farm', 'health_food'}
COFFEE_SHOP = {'coffee', 'bakery', 'pastry', 'tea'}
FOOD = {'restaurant', 'fast_food', 'bar', 'pub', 'food_court', 'biergarten', 'ice_cream'}
FUN_AMENITY = {'cinema', 'theatre', 'arts_centre', 'nightclub', 'music_venue'}
FUN_TOURISM = {'museum', 'gallery'}
FUN_LEISURE = {'bowling_alley', 'amusement_arcade', 'escape_game', 'miniature_golf'}
PARK = {'park', 'playground', 'garden', 'nature_reserve', 'dog_park'}
SHOP_SKIP = {'car', 'car_repair', 'car_parts', 'tyres', 'motorcycle', 'boat', 'truck', 'caravan',
             'storage_rental', 'vacant', 'no', 'yes', 'fuel', 'gas', 'trade', 'wholesale',
             'funeral_directors', 'rental', 'trailer', 'agrarian', 'industrial'}


def classify(tags):
    a = tags.get('amenity'); s = tags.get('shop'); l = tags.get('leisure'); t = tags.get('tourism')
    if s in GROCERY or a == 'marketplace':
        return 'grocery', s or a
    if a == 'cafe' or s in COFFEE_SHOP:
        return 'coffee', a if a == 'cafe' else s
    if a in FOOD:
        return 'food', a
    if a == 'library' or s == 'books':
        return 'books', a if a == 'library' else s
    if a in FUN_AMENITY or t in FUN_TOURISM or l in FUN_LEISURE:
        return 'fun', a if a in FUN_AMENITY else (t if t in FUN_TOURISM else l)
    if a == 'bank':
        return 'bank', a
    if a == 'school':
        return 'school', a
    if l in PARK:
        if tags.get('access') in ('private', 'no'):
            return None, None
        return 'park', l
    if s and s not in SHOP_SKIP:
        return 'shop', s
    return None, None


def is_link_station(tags):
    if tags.get('railway') != 'station' and tags.get('public_transport') != 'station':
        return False
    blob = ' '.join(tags.get(k, '') for k in ('station', 'network', 'operator', 'light_rail', 'name', 'line'))
    return 'light_rail' in blob or 'Link' in blob or tags.get('light_rail') == 'yes'


def inside(lon, lat):
    return BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


def densify(ring, step_m=60.0):
    """Yield points along a ring every step_m metres."""
    pts = [(n.lon, n.lat) for n in ring if n.location.valid()]
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx = (x1 - x0) * 111320 * math.cos(math.radians(y0)); dy = (y1 - y0) * 110540
        d = math.hypot(dx, dy)
        k = max(1, int(d // step_m))
        for i in range(k):
            f = i / k
            out.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
    return out or pts


def main():
    pbf = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work = os.path.join(root, 'data', 'work'); os.makedirs(work, exist_ok=True)
    fp = (osmium.FileProcessor(pbf)
          .with_locations()
          .with_areas()
          .with_filter(osmium.filter.KeyFilter('amenity', 'shop', 'leisure', 'tourism', 'railway', 'public_transport')))
    n_poi = n_park_pts = 0
    stations = {}
    with open(os.path.join(work, 'pois.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['lat', 'lon', 'cat', 'name', 'kind'])
        for o in fp:
            if o.is_way():
                continue  # closed ways come back as areas
            tags = {t.k: t.v for t in o.tags}
            if o.is_node():
                if not o.location.valid():
                    continue
                lon, lat = o.location.lon, o.location.lat
                ring_pts = None
            elif o.is_area():
                ring_pts = None
                rings = list(o.outer_rings())
                if not rings:
                    continue
                pts = [(n.lon, n.lat) for n in rings[0] if n.location.valid()]
                if not pts:
                    continue
                lon = sum(p[0] for p in pts) / len(pts); lat = sum(p[1] for p in pts) / len(pts)
                ring_pts = rings
            else:
                continue
            if not inside(lon, lat):
                continue
            if is_link_station(tags):
                name = tags.get('name', '').replace(' Station', '')
                if name and name not in stations:
                    stations[name] = (lat, lon)
            cat, kind = classify(tags)
            if not cat:
                continue
            name = tags.get('name', '')
            if cat == 'park' and ring_pts is not None:
                # centre point carries the name; boundary points carry the distance
                w.writerow([f'{lat:.6f}', f'{lon:.6f}', 'park_c', name, kind]); n_poi += 1
                for ring in ring_pts:
                    for (x, y) in densify(ring):
                        w.writerow([f'{y:.6f}', f'{x:.6f}', 'park', '', kind]); n_park_pts += 1
            else:
                w.writerow([f'{lat:.6f}', f'{lon:.6f}', cat, name, kind]); n_poi += 1
    with open(os.path.join(work, 'stations.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['lat', 'lon', 'name'])
        for name, (lat, lon) in sorted(stations.items()):
            w.writerow([f'{lat:.6f}', f'{lon:.6f}', name])
    print('places', n_poi, 'park boundary points', n_park_pts, 'link stations', len(stations))


if __name__ == '__main__':
    main()
