"""How much of Dhaka is within 10 / 15 minutes by car of a 24-hour emergency department?

Run from the repository root (needs GEOAPIFY_API_KEY; about 150 credits the first time, isolines are cached in
benchmark/.cache/ so later runs only cost 2 requests):
    python benchmark/coverage.py

Method (standard library only):
1. Dhaka Metropolitan boundary (ঢাকা মহানগর, OSM admin_level 6) from the Geoapify Boundaries API.
2. All `healthcare.hospital` places in and around it (Places API), classified with docs/app/facility_rules.json.
   Set A: confirmed general 24h emergency departments + government general hospitals ("emergency expected").
   Set B: set A + medical college hospitals (the classifier's "major" hospitals).
   Entries of one campus (within 300 m) are merged.
3. One Isoline API request per hospital: areas reachable by car in 10 and 15 minutes, traffic=approximated.
   Isolines go outwards from the hospital; we use them as "minutes to reach the hospital" (an approximation:
   one-way streets differ).
4. A 300 m grid over the boundary; each point is covered if it lies inside any hospital's isoline.

Writes benchmark/coverage.md and docs/app/coverage.json (used by docs/app/coverage.html).
"""

import json
import math
import os
import sys
import urllib.parse
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dhaka_emergency.classify import classify  # noqa: E402
from dhaka_emergency.finder import haversine_m  # noqa: E402
from dhaka_emergency.geoapify import GeoapifyClient  # noqa: E402

CACHE = os.path.join(ROOT, "benchmark", ".cache")
GRID_M = 300
MERGE_M = 300
RANGES = (600, 900)


def boundary(client):
    """Dhaka Metropolitan (admin_level 6) polygon, simplified to ~1000 points."""
    d = client._request("https://api.geoapify.com/v1/boundaries/part-of",
                        {"lat": 23.78, "lon": 90.40, "geometry": "geometry_1000"})
    for f in d.get("features", []):
        raw = (f["properties"].get("datasource") or {}).get("raw") or {}
        if str(raw.get("admin_level")) == "6":
            return f
    raise SystemExit("Dhaka Metropolitan boundary not found")


def rings(geom):
    """Polygon / MultiPolygon -> list of polygons, each a list of rings [(lon, lat), ...]."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return list(geom["coordinates"])


def in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def in_polys(x, y, polys):
    for poly in polys:
        if in_ring(x, y, poly[0]) and not any(in_ring(x, y, hole) for hole in poly[1:]):
            return True
    return False


def bbox(polys):
    xs = [p[0] for poly in polys for p in poly[0]]
    ys = [p[1] for poly in polys for p in poly[0]]
    return min(xs), min(ys), max(xs), max(ys)


def hospitals(client, box):
    """Hospitals within the boundary's box plus ~3 km, classified."""
    pad = 0.03
    rect = "rect:%.4f,%.4f,%.4f,%.4f" % (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
    q = urllib.parse.urlencode({"categories": "healthcare.hospital", "filter": rect, "limit": 500}, safe=",:")
    out, seen = [], set()
    for f in client._request("https://api.geoapify.com/v2/places?" + q).get("features", []):
        p = f["properties"]
        raw = (p.get("datasource") or {}).get("raw") or {}
        c = classify({"name": p.get("name"), "nameEn": raw.get("name:en"), "nameBn": raw.get("name:bn"),
                      "tags": {k: raw.get(k) for k in ("emergency", "healthcare", "healthcare:speciality",
                                                       "operator:type") if raw.get(k)}})
        if c["confirmed"]:
            seen.add(c["confirmed"]["id"])
        general_er = (c["ed"] == "confirmed" and not c["speciality"]) or c["ed"] == "yes"
        if general_er or c["major"]:
            out.append({"name": raw.get("name:en") or p.get("name"), "lon": p["lon"], "lat": p["lat"],
                        "set": "A" if general_er else "B", "ed": c["ed"]})
    # one entry per campus (A wins over B)
    out.sort(key=lambda h: h["set"])
    kept = []
    for h in out:
        if not any(haversine_m(h["lon"], h["lat"], k["lon"], k["lat"]) < MERGE_M for k in kept):
            kept.append(h)
    return kept, seen


def isoline(client, h):
    os.makedirs(CACHE, exist_ok=True)
    key = "iso_%.5f_%.5f_%s.json" % (h["lon"], h["lat"], "-".join(map(str, RANGES)))
    path = os.path.join(CACHE, key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    d = client.isoline(h["lon"], h["lat"], ranges_s=RANGES, mode="drive")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    return d


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    client = GeoapifyClient()
    bnd = boundary(client)
    bpolys = rings(bnd["geometry"])
    box = bbox(bpolys)
    hs, seen = hospitals(client, box)
    with open(os.path.join(ROOT, "docs", "app", "facility_rules.json"), encoding="utf-8") as fh:
        missing = [c["name"] for c in json.load(fh)["confirmed"] if c["scope"] == "general" and c["id"] not in seen]
    for h in hs:
        d = isoline(client, h)
        h["iso"] = {f["properties"]["range"]: rings(f["geometry"]) for f in d.get("features", [])}
        h["iso_bbox"] = {r: bbox(p) for r, p in h["iso"].items()}

    # grid
    lat0 = (box[1] + box[3]) / 2
    dlat = GRID_M / 111320.0
    dlon = GRID_M / (111320.0 * math.cos(math.radians(lat0)))
    points = []
    y = box[1] + dlat / 2
    while y < box[3]:
        x = box[0] + dlon / 2
        while x < box[2]:
            if in_polys(x, y, bpolys):
                points.append((x, y))
            x += dlon
        y += dlat

    def covered(x, y, rng, sets):
        for h in hs:
            if h["set"] not in sets or rng not in h["iso"]:
                continue
            b = h["iso_bbox"][rng]
            if b[0] <= x <= b[2] and b[1] <= y <= b[3] and in_polys(x, y, h["iso"][rng]):
                return True
        return False

    grid = []
    stats = {}
    for x, y in points:
        cell = {"x": round(x, 5), "y": round(y, 5)}
        for sets, tag in ((("A",), "a"), (("A", "B"), "b")):
            m = 10 if covered(x, y, 600, sets) else (15 if covered(x, y, 900, sets) else 0)
            cell[tag] = m
            for lim in (10, 15):
                stats[(tag, lim)] = stats.get((tag, lim), 0) + (1 if m and m <= lim else 0)
        grid.append(cell)

    n = len(points)
    area_km2 = n * (GRID_M / 1000.0) ** 2
    pct = {k: 100.0 * v / n for k, v in stats.items()}
    na = sum(1 for h in hs if h["set"] == "A")
    nb = len(hs)

    out_json = {"date": date.today().isoformat(), "grid_m": GRID_M, "boundary": bnd["geometry"],
                "hospitals": [{k: h[k] for k in ("name", "lon", "lat", "set", "ed")} for h in hs],
                "grid": grid, "pct": {f"{k[0]}{k[1]}": round(v, 1) for k, v in pct.items()}}
    with open(os.path.join(ROOT, "docs", "app", "coverage.json"), "w", encoding="utf-8") as fh:
        json.dump(out_json, fh, ensure_ascii=False, separators=(",", ":"))

    lines = [
        f"# Emergency coverage of Dhaka ({date.today().isoformat()})", "",
        "Generated by `python benchmark/coverage.py`. Interactive map: "
        "[coverage map](https://abdullah-atif.github.io/dhaka-emergency-finder/app/coverage.html).", "",
        f"Area: Dhaka Metropolitan (OSM boundary ঢাকা মহানগর, from the Geoapify Boundaries API), {n} grid points "
        f"every {GRID_M} m ≈ {area_km2:.0f} km². Travel by car with Geoapify's approximated traffic.", "",
        "| Hospitals counted | Hospitals | Area within 10 min | Area within 15 min |",
        "|---|---|---|---|",
        f"| **A:** confirmed 24h emergency + government general hospitals | {na} | "
        f"{pct[('a', 10)]:.0f}% | {pct[('a', 15)]:.0f}% |",
        f"| **B:** A + medical college hospitals | {nb} | {pct[('b', 10)]:.0f}% | {pct[('b', 15)]:.0f}% |",
        "",
        "## Hospitals used", "",
        "| Set | Hospital | Classifier |", "|---|---|---|",
    ]
    for h in sorted(hs, key=lambda h: (h["set"], h["name"] or "")):
        lines.append(f"| {h['set']} | {h['name']} | {h['ed']} |")
    lines += [
        "", "## Caveats", "",
        "- **Area, not people.** Each grid point counts the same; dense and empty areas weigh equally.",
        "- **Approximated traffic** is Geoapify's typical-traffic model, not a specific hour. Rush hour is slower.",
        "- **Direction.** Isolines go outwards from each hospital; we read them as \"minutes to reach it\". One-way "
        "streets make the two directions differ.",
        "- **Map data.** A hospital missing from OpenStreetMap, or not recognised by its name, is not counted. "
        "Set A includes only the hospitals our rules can defend (see "
        "[classifier evaluation](classify_eval.md)); private hospitals with emergency units are not in A.",
        f"- Entries of one campus within {MERGE_M} m are merged before requesting isolines.",
    ]
    if missing:
        lines.append("- **Not in the map data as a hospital** (so not counted, although its 24h emergency department "
                     "is confirmed): " + ", ".join(missing) + ".")
    with open(os.path.join(ROOT, "benchmark", "coverage.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{n} points, {area_km2:.0f} km2; A={na} hospitals, B={nb}; "
          + ", ".join(f"{k[0]}{k[1]}={v:.1f}%" for k, v in sorted(pct.items())))


if __name__ == "__main__":
    main()
