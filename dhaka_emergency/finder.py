"""Find emergency facilities and rank them by travel time."""

import math
import re
from dataclasses import dataclass, field

from .classify import classify

EMERGENCY_NUMBER = "999"  # Bangladesh national emergency service

CATEGORIES = {
    "hospital": ["healthcare.hospital"],
    "clinic": ["healthcare.clinic_or_praxis"],
    "pharmacy": ["healthcare.pharmacy"],
    "police": ["service.police"],
    "fire": ["service.fire_station"],
    "ambulance": ["emergency.ambulance_station"],
}

# Search radius grows until enough candidates are found (metres).
RADII = (2000, 5000, 10000)
MAX_CANDIDATES = 10

_LATLON = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass
class Origin:
    lon: float
    lat: float
    label: str
    # True when the geocoder only matched the city/district, not the place itself.
    coarse: bool = False


@dataclass
class Facility:
    name: str
    address: str
    lon: float
    lat: float
    straight_m: float
    phone: str = ""
    drive_m: float = None
    drive_s: float = None
    categories: list = field(default_factory=list)
    # classify.py result for hospitals and clinics: ed = confirmed / yes / likely / specialised / unknown / no
    cls: dict = None
    opening_hours: str = ""

    @property
    def maybe_not_er(self):
        """Not a general emergency hospital: a non-hospital, or one speciality only (see classify.py)."""
        return bool(self.cls) and self.cls["ed"] in ("no", "specialised")


def haversine_m(lon1, lat1, lon2, lat2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _norm(name):
    return re.sub(r"[^a-z0-9ঀ-৿]+", "", (name or "").lower())


def same_place(a, b):
    """Same name (or one name is the start of the other, e.g. "X" and "X, Government hospital, Road, Dhaka")
    and close together. Mirrors dedupe() in docs/app/app.js."""
    x, y = _norm(a.name), _norm(b.name)
    if not x or not y or a.name.startswith("(unnamed)") or b.name.startswith("(unnamed)"):
        return False
    d = haversine_m(a.lon, a.lat, b.lon, b.lat)
    if x == y:
        return d < 30 or (len(x) >= 12 and d < 300)
    shorter, longer = sorted((x, y), key=len)
    return len(shorter) >= 12 and longer.startswith(shorter) and d < 300


def dedupe(facilities):
    """Merge duplicates, keeping the nearer one, the shorter name and any phone number."""
    out = []
    for f in facilities:
        g = next((o for o in out if same_place(o, f)), None)
        if g is None:
            out.append(f)
            continue
        if len(f.name) < len(g.name):
            g.name = f.name
        g.phone = g.phone or f.phone
    return out


def resolve_origin(client, where):
    """Accepts "lat,lon" or free text (English or Bangla)."""
    m = _LATLON.match(where)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        return Origin(lon=lon, lat=lat, label=f"{lat:.5f},{lon:.5f}")
    hit = client.geocode(where)
    if not hit:
        return None
    # e.g. "Dhanmondi 27, Dhaka" -> only "Dhaka" matched (match_type "match_by_city_or_disrict")
    match_type = (hit.get("rank") or {}).get("match_type", "")
    coarse = match_type.startswith(("match_by_city", "match_by_country"))
    return Origin(lon=hit["lon"], lat=hit["lat"], label=hit.get("formatted", where), coarse=coarse)


def _phone(props):
    contact = props.get("contact") or {}
    raw = (props.get("datasource") or {}).get("raw") or {}
    return contact.get("phone") or raw.get("phone") or raw.get("contact:phone") or ""


def _to_facility(feature, origin):
    p = feature.get("properties", {})
    raw = (p.get("datasource") or {}).get("raw") or {}
    cats = p.get("categories", [])
    cls = None
    if "healthcare.hospital" in cats or "healthcare.clinic_or_praxis" in cats:
        cls = classify({"name": p.get("name"), "nameEn": raw.get("name:en"), "nameBn": raw.get("name:bn"),
                        "tags": {k: raw.get(k) for k in ("emergency", "healthcare", "healthcare:speciality",
                                                         "operator:type") if raw.get(k)}})
    lon, lat = p.get("lon"), p.get("lat")
    if lon is None or lat is None:
        lon, lat = feature["geometry"]["coordinates"][:2]
    return Facility(
        # Prefer the English name (OSM name:en); for unnamed places show the building/street as a hint.
        name=(((p.get("datasource") or {}).get("raw") or {}).get("name:en") or p.get("name")
              or ("(unnamed) · " + p["address_line1"] if p.get("address_line1") else "(unnamed)")),
        address=p.get("address_line2") or p.get("formatted") or "",
        lon=lon,
        lat=lat,
        straight_m=haversine_m(origin.lon, origin.lat, lon, lat),
        phone=_phone(p),
        categories=cats,
        cls=cls,
        opening_hours=str(raw.get("opening_hours") or ""),
    )


def find_candidates(client, origin, kind, want=MAX_CANDIDATES):
    cats = CATEGORIES[kind]
    features = []
    for radius in RADII:
        features = client.places(origin.lon, origin.lat, cats, radius, limit=want)
        if len(features) >= min(want, 5):
            break
    facilities = [_to_facility(f, origin) for f in features]
    facilities.sort(key=lambda f: f.straight_m)
    facilities = dedupe(facilities)
    return facilities[:want]


def rank_by_travel_time(client, origin, facilities, mode="drive"):
    if not facilities:
        return []
    cells = client.route_matrix(
        (origin.lon, origin.lat), [(f.lon, f.lat) for f in facilities], mode=mode
    )
    for f, cell in zip(facilities, cells):
        if cell:
            f.drive_m, f.drive_s = cell["distance"], cell["time"]
    reachable = [f for f in facilities if f.drive_s is not None]
    unreachable = [f for f in facilities if f.drive_s is None]
    reachable.sort(key=lambda f: f.drive_s)
    ranked = reachable + unreachable
    # Keep the travel-time order, but move places classified as "not an emergency facility" to the end.
    return [f for f in ranked if not (f.cls and f.cls["ed"] == "no")] + \
        [f for f in ranked if f.cls and f.cls["ed"] == "no"]


def find(client, where, kind="hospital", mode="drive", top=5):
    """Full pipeline: geocode -> places -> route matrix -> ranked list."""
    origin = resolve_origin(client, where)
    if origin is None:
        return None, []
    candidates = find_candidates(client, origin, kind)
    ranked = rank_by_travel_time(client, origin, candidates, mode=mode)
    return origin, ranked[:top]
