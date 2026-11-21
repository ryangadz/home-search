# Home search: big garages, walkable streets

A personal map of King County houses that have a lot of garage space, set against
how much there is to walk to.

**Live map: https://ryangadz.github.io/home-search/**

To run it locally, open `web/index.html` in a browser. It needs an internet
connection for the street map only.

- **Dots** are houses whose county record shows 600+ sq ft of garage (attached,
  basement and detached added together). Bigger dot, bigger garage.
- **Blue shading** is walkability, 0 to 100. Darker means more within walking distance.
- **Sliders** set the minimum garage space and walkability. "More filters" adds house
  size, county appraised value and lot size.
- Click a house for its details and links to the official Walk Score, Zillow,
  Street View and the county record.

The map shows every house that qualifies, whether or not it is for sale. Use it to
find the streets worth watching, then set listing alerts for those areas.

## Where the data comes from

| What | Source | File in `data/raw/` |
|---|---|---|
| Garage, house and lot facts | King County Assessor data download (Residential Building, Accessory, Parcel, Lookup, Real Property Account) | `EXTR_*.csv` |
| A map point, address and appraised value per parcel | King County GIS "Parcels with Address" layer | `kc_parcel_address_slim.csv` |
| Shops, cafes, parks, streets and paths | OpenStreetMap, Geofabrik Washington extract | `washington-*.osm.pbf` |

The Assessor asks that its data not be used to build commercial lists of
individuals. Nothing here holds owner names.

The built data in `web/data/` is committed so the page works straight from the repo.
The raw downloads (about 1.1 GB) are not.

## Rebuilding

Python 3.10+ with `pandas`, `scipy` and `osmium` (`pip install pandas scipy osmium`).

```
python scripts/01_slim_parcels.py <downloaded parcel-address CSV>   # only after a fresh download
python scripts/02_extract_osm.py data/raw/washington-XXXXXX.osm.pbf # places and stations
python scripts/02b_walk_network.py data/raw/washington-XXXXXX.osm.pbf
python scripts/02c_walk_field.py                                    # walking distances
python scripts/03_build.py                                          # writes web/data/*.js
python scripts/check_points.py                                      # compare with official Walk Scores
```

The whole chain takes about two minutes.

## How walkability is worked out

It follows the published Walk Score recipe: the nearest grocery, restaurants,
shops, coffee, bank, park, school, library or bookshop and entertainment each earn
points, and the points fade with walking distance (full credit inside a quarter
mile, none past a mile and a half). The nearest place in each category is measured
along the OpenStreetMap walking network, so lakes, freeways and cul-de-sacs count.

It is this project's own estimate, not the official Walk Score. Against 35 official
scores looked up on 2026-11-20 it is off by about 7 points on average and by as
much as 22 at single spots; it is closest (about 4 points) where the official score
is 80 or more. The fade curve was tuned on those same points, so expect slightly
larger errors elsewhere. Every house links to its official score.

## Known limits

- The county records floor area, not door height, so an "RV size" garage here means
  floor area only. County notes mentioning a shop, barn or RV are shown on the house.
- Some very large "garages" are commercial lots with a house on them. The county use
  and zoning are shown on each house.
- Places come from OpenStreetMap volunteers; a missing shop lowers a score.
- Only King County is covered.

## Ideas not built yet

- Mark houses that are for sale or rent now (for example from a Redfin search download).
- Door-to-door transit time to chosen offices.
- Snohomish and Pierce counties.

## Credits

- Places, streets and paths: © OpenStreetMap contributors, under the Open Database
  License. `web/data/places.js` and the walkability grid are derived from it.
- House, garage and parcel facts: King County Department of Assessments and King County GIS.
- Street map tiles: Esri and its data providers.
- Map library: Leaflet (BSD 2-Clause). Typeface: Archivo (SIL Open Font License).
