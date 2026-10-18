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
    "worship": ["religion.place_of_worship"],
}
EMERGENCY_KINDS = {"hospital", "clinic", "pharmacy", "police", "fire", "ambulance"}

# --religion values for --type worship, with what the place is usually called
RELIGIONS = {
    "islam": "mosque",
    "hinduism": "temple",
    "christianity": "church",
    "buddhism": "Buddhist temple",
    "sikhism": "gurdwara",
    "judaism": "synagogue",
    "multifaith": "multi-faith place",
}

# The mapped outline can be one building or a whole compound (e.g. a temple complex).
SIZE_OWN = "mapped outline"
SIZE_HOST = "containing building"

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
    place_id: str = ""
    area_m2: float = None
    area_source: str = ""

    @property
    def religion(self):
        prefix = "religion.place_of_worship."
        return next((c[len(prefix):] for c in self.categories if c.startswith(prefix)), "")


def haversine_m(lon1, lat1, lon2, lat2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _ring_area_m2(ring):
    # Local equirectangular projection: accurate enough for a single building.
    r = 6371000.0
    lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
    pts = [(math.radians(x) * r * math.cos(lat0), math.radians(y) * r) for x, y in ring]
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1]
                   for i in range(len(pts)))) / 2


def polygon_area_m2(geometry):
    """Area of a GeoJSON Polygon/MultiPolygon in m² (holes subtracted), else None."""
    if not geometry:
        return None
    if geometry.get("type") == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry.get("type") == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        return None
    total = 0.0
    for rings in polygons:
        total += _ring_area_m2(rings[0]) - sum(_ring_area_m2(h) for h in rings[1:])
    return total


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
        # address_line1 is the street for unnamed places, so it is not a name fallback.
        name=p.get("name") or "(unnamed)",
        address=p.get("address_line2") or p.get("formatted") or "",
        lon=lon,
        lat=lat,
        straight_m=haversine_m(origin.lon, origin.lat, lon, lat),
        phone=_phone(p),
        categories=p.get("categories", []),
        place_id=p.get("place_id", ""),
    )


def categories_for(kind, religion=None):
    if kind == "worship" and religion:
        return [f"religion.place_of_worship.{religion}"]
    return CATEGORIES[kind]


def add_sizes(client, facilities):
    """Fill area_m2 from Place Details. The place's own outline is preferred;
    the containing building (e.g. a mosque inside a market) is only an upper bound."""
    for f in facilities:
        if not f.place_id:
            continue
        found = {}
        for feat in client.place_details(f.place_id):
            kind = (feat.get("properties") or {}).get("feature_type")
            area = polygon_area_m2(feat.get("geometry"))
            if kind in ("details", "building") and area:
                found.setdefault(kind, area)
        if "details" in found:
            f.area_m2, f.area_source = found["details"], SIZE_OWN
        elif "building" in found:
            f.area_m2, f.area_source = found["building"], SIZE_HOST


def find_candidates(client, origin, kind, want=MAX_CANDIDATES, religion=None):
    cats = categories_for(kind, religion)
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


def find(client, where, kind="hospital", mode="drive", top=5, religion=None, sort="time"):
    """Full pipeline: geocode -> places -> route matrix -> ranked list.
    For places of worship, sizes come from Place Details (sort="size" = biggest first)."""
    origin = resolve_origin(client, where)
    if origin is None:
        return None, []
    candidates = find_candidates(client, origin, kind, religion=religion)
    ranked = rank_by_travel_time(client, origin, candidates, mode=mode)
    if kind != "worship":
        return origin, ranked[:top]
    if sort == "size":
        add_sizes(client, ranked)
        ranked.sort(key=lambda f: -(f.area_m2 or 0))
        return origin, ranked[:top]
    ranked = ranked[:top]
    add_sizes(client, ranked)
    return origin, ranked
