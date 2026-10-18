"""Find emergency facilities and rank them by travel time."""

import math
import re
from dataclasses import dataclass, field

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


def haversine_m(lon1, lat1, lon2, lat2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def resolve_origin(client, where):
    """Accepts "lat,lon" or free text (English or Bangla)."""
    m = _LATLON.match(where)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        return Origin(lon=lon, lat=lat, label=f"{lat:.5f},{lon:.5f}")
    hit = client.geocode(where)
    if not hit:
        return None
    return Origin(lon=hit["lon"], lat=hit["lat"], label=hit.get("formatted", where))


def _phone(props):
    contact = props.get("contact") or {}
    raw = (props.get("datasource") or {}).get("raw") or {}
    return contact.get("phone") or raw.get("phone") or raw.get("contact:phone") or ""


def _to_facility(feature, origin):
    p = feature.get("properties", {})
    lon, lat = p.get("lon"), p.get("lat")
    if lon is None or lat is None:
        lon, lat = feature["geometry"]["coordinates"][:2]
    return Facility(
        name=p.get("name") or p.get("address_line1") or "(unnamed)",
        address=p.get("address_line2") or p.get("formatted") or "",
        lon=lon,
        lat=lat,
        straight_m=haversine_m(origin.lon, origin.lat, lon, lat),
        phone=_phone(p),
        categories=p.get("categories", []),
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
    return reachable + unreachable


def find(client, where, kind="hospital", mode="drive", top=5):
    """Full pipeline: geocode -> places -> route matrix -> ranked list."""
    origin = resolve_origin(client, where)
    if origin is None:
        return None, []
    candidates = find_candidates(client, origin, kind)
    ranked = rank_by_travel_time(client, origin, candidates, mode=mode)
    return origin, ranked[:top]
