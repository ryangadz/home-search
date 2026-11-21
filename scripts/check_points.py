"""Compare our walkability estimate with official Walk Scores looked up by hand.

Usage: python3 scripts/check_points.py
Official values were read from walkscore.com/score/loc/lat=..,lng=.. on 2026-11-20.
"""
import numpy as np
import walklib as wl

OFFICIAL = [
 ('Capitol Hill, Broadway & John', 47.6196, -122.3209, 99), ('Ballard, Market & 22nd', 47.6686, -122.3847, 96),
 ('Wallingford, 45th & Wallingford', 47.6614, -122.3360, 97), ('Downtown Bellevue', 47.6176, -122.2012, 93),
 ('Queen Anne top', 47.6390, -122.3570, 95), ('West Seattle Junction', 47.5610, -122.3870, 97),
 ('Downtown Kirkland', 47.6769, -122.2060, 93), ('Downtown Redmond', 47.6740, -122.1215, 95),
 ('Magnolia village', 47.6393, -122.3990, 89), ('Laurelhurst', 47.6590, -122.2790, 25),
 ('View Ridge', 47.6800, -122.2790, 35), ('Enatai', 47.5870, -122.1960, 31),
 ('Education Hill', 47.6920, -122.1180, 32), ('Bridle Trails', 47.6500, -122.1700, 5),
 ('Sammamish, 228th & SE 8th', 47.6018, -122.0356, 55), ('Issaquah Highlands', 47.5430, -122.0000, 36),
 ('Mercer Island town center', 47.5870, -122.2350, 81), ('Medina', 47.6210, -122.2280, 33),
 ('sample', 47.41553, -122.07632, 6), ('sample', 47.75553, -122.36929, 21), ('sample', 47.48107, -122.31591, 28),
 ('sample', 47.5109, -122.33906, 38), ('sample', 47.45992, -122.35184, 36), ('sample', 47.39219, -122.21044, 26),
 ('sample', 47.6368, -122.15936, 23), ('sample', 47.66192, -122.19826, 72), ('sample', 47.45424, -122.27659, 46),
 ('sample', 47.62759, -122.31168, 86), ('sample', 47.62707, -122.30961, 89), ('sample', 47.44265, -122.15065, 55),
 ('sample', 47.76644, -122.20662, 86), ('sample', 47.64261, -122.39446, 82), ('sample', 47.6624, -122.36343, 86),
 ('sample', 47.72508, -122.04566, 2), ('sample', 47.25783, -122.21953, 13),
]

if __name__ == '__main__':
    W = wl.Walk()
    P = wl.to_xy([p[1] for p in OFFICIAL], [p[2] for p in OFFICIAL])
    ours, parts, detour, _, _ = W.score(P, parts=True)
    off = np.array([p[3] for p in OFFICIAL], float)
    for i, p in enumerate(OFFICIAL):
        print(f"{off[i]:3.0f} official  {ours[i]:3.0f} ours  {ours[i]-off[i]:+4.0f}  {p[0]:32s} "
              + ' '.join(f"{c[:4]}={parts[c][i]:.2f}" for c in wl.WEIGHTS))
    err = ours - off
    print(f"\nmean error {err.mean():+.1f}, mean absolute error {np.abs(err).mean():.1f}, worst {np.abs(err).max():.0f}, n={len(off)}")
    for lo, hi in [(0, 50), (50, 80), (80, 101)]:
        m = (off >= lo) & (off < hi)
        print(f"  official {lo}-{hi}: n={m.sum()}, mean error {err[m].mean():+.1f}, mean abs {np.abs(err[m]).mean():.1f}")
