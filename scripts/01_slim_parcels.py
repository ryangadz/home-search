"""Slim the King County 'Parcels with Address' CSV down to the columns the map needs.

Usage: python3 scripts/01_slim_parcels.py <full_parcel_address.csv>
Writes data/raw/kc_parcel_address_slim.csv (one row per parcel, with a map coordinate).
Taxpayer / mailing columns in the source are deliberately not carried over.
"""
import sys, os
import pandas as pd

KEEP = ['PIN', 'ADDR_FULL', 'ZIP5', 'CTYNAME', 'POSTALCTYNAME', 'LAT', 'LON',
        'LOTSQFT', 'APPRLNDVAL', 'APPR_IMPR', 'KCA_ZONING', 'PREUSE_DESC', 'PROPTYPE']

src = sys.argv[1]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, 'data', 'raw', 'kc_parcel_address_slim.csv')
first = True
n = 0
for chunk in pd.read_csv(src, usecols=KEEP, dtype=str, chunksize=100_000, encoding='utf-8-sig'):
    chunk = chunk[KEEP]
    for c in chunk.columns:
        chunk[c] = chunk[c].str.strip()
    chunk.to_csv(out, mode='w' if first else 'a', header=first, index=False)
    first = False
    n += len(chunk)
print('wrote', out, n, 'rows')
