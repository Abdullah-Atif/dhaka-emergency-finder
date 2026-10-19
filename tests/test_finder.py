"""Unit tests with a fake client, so they run without an API key or network.

Run: python -m unittest discover -s tests
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dhaka_emergency import finder  # noqa: E402
from dhaka_emergency.mapview import write_map  # noqa: E402


def feature(name, lon, lat, phone=None, place_id=None, categories=None):
    props = {"name": name, "lon": lon, "lat": lat, "address_line2": f"{name} road, Dhaka"}
    if phone:
        props["datasource"] = {"raw": {"phone": phone}}
    if place_id:
        props["place_id"] = place_id
    if categories:
        props["categories"] = categories
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Point", "coordinates": [lon, lat]}}


def square(lon, lat, side_m):
    """GeoJSON square polygon of side_m metres centred on (lon, lat)."""
    import math
    dlat = side_m / 2 / 111195.0
    dlon = dlat / math.cos(math.radians(lat))
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat],
            [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]
    return {"type": "Polygon", "coordinates": [ring]}


class FakeClient:
    """Mimics GeoapifyClient. Hospital A is closest in a straight line
    but slowest by road (e.g. across a canal); B is the fastest."""

    api_key = "test-key"

    def __init__(self):
        self.calls = []

    def geocode(self, text):
        self.calls.append(("geocode", text))
        if "nowhere" in text:
            return None
        return {"lon": 90.3654, "lat": 23.8069, "formatted": "Mirpur 10, Dhaka"}

    def places(self, lon, lat, categories, radius_m, limit=20):
        self.calls.append(("places", tuple(categories), radius_m))
        if categories[0].startswith("religion"):
            islam = ["religion", "religion.place_of_worship", "religion.place_of_worship.islam"]
            hindu = ["religion", "religion.place_of_worship", "religion.place_of_worship.hinduism"]
            return [
                feature("A Hospital", 90.3660, 23.8075, place_id="small-mosque", categories=islam),
                feature("B Hospital", 90.3700, 23.8100, place_id="market-mosque", categories=islam),
                feature("C Hospital", 90.3800, 23.8200, place_id="temple", categories=hindu),
                feature("D Hospital", 90.3900, 23.8300, place_id="no-outline", categories=islam),
                feature("E Hospital", 90.4000, 23.8400, categories=islam),
            ]
        if radius_m < 5000:
            return [feature("A Hospital", 90.3660, 23.8075)]  # too few -> widen
        return [
            feature("A Hospital", 90.3660, 23.8075),
            feature("B Hospital", 90.3700, 23.8100, phone="+880 2 0000000"),
            feature("C Hospital", 90.3800, 23.8200),
            feature("D Hospital", 90.3900, 23.8300),
            feature("E Hospital", 90.4000, 23.8400),
        ]

    def route_matrix(self, source, targets, mode="drive"):
        self.calls.append(("route_matrix", mode, len(targets)))
        times = {90.3660: 1500, 90.3700: 420, 90.3800: 900, 90.3900: None, 90.4000: 1200}
        out = []
        for lon, _lat in targets:
            t = times[lon]
            out.append(None if t is None else {"distance": t * 8, "time": t})
        return out

    def place_details(self, place_id):
        self.calls.append(("place_details", place_id))
        own = {"properties": {"feature_type": "details"}, "geometry": square(90.3660, 23.8075, 20)}
        host = {"properties": {"feature_type": "building"}, "geometry": square(90.3700, 23.8100, 50)}
        point = {"properties": {"feature_type": "details"},
                 "geometry": {"type": "Point", "coordinates": [90.39, 23.83]}}
        return {
            "small-mosque": [own, host],     # own outline wins over the host building
            "market-mosque": [point, host],  # only the containing building is known
            "temple": [{"properties": {"feature_type": "details"},
                        "geometry": square(90.38, 23.82, 30)}],
            "no-outline": [point],
        }[place_id]

    def route(self, start, end, mode="drive"):
        return {"type": "Feature", "properties": {"time": 420},
                "geometry": {"type": "LineString", "coordinates": [list(start), list(end)]}}


class FinderTests(unittest.TestCase):
    def test_ranks_by_travel_time_not_distance(self):
        origin, ranked = finder.find(FakeClient(), "Mirpur 10", kind="hospital", top=5)
        self.assertEqual(origin.label, "Mirpur 10, Dhaka")
        self.assertEqual([f.name for f in ranked],
                         ["B Hospital", "C Hospital", "E Hospital", "A Hospital", "D Hospital"])
        self.assertIsNone(ranked[-1].drive_s)  # unreachable goes last

    def test_widens_radius_when_too_few_results(self):
        client = FakeClient()
        finder.find(client, "Mirpur 10")
        radii = [c[2] for c in client.calls if c[0] == "places"]
        self.assertEqual(radii, [2000, 5000])

    def test_uses_correct_category(self):
        client = FakeClient()
        finder.find(client, "Mirpur 10", kind="pharmacy")
        self.assertIn(("places", ("healthcare.pharmacy",), 2000), client.calls)

    def test_latlon_input_skips_geocoding(self):
        client = FakeClient()
        origin, _ = finder.find(client, "23.8069, 90.3654")
        self.assertAlmostEqual(origin.lat, 23.8069)
        self.assertAlmostEqual(origin.lon, 90.3654)
        self.assertFalse(any(c[0] == "geocode" for c in client.calls))

    def test_unknown_location(self):
        origin, ranked = finder.find(FakeClient(), "nowhere at all")
        self.assertIsNone(origin)
        self.assertEqual(ranked, [])

    def test_phone_extracted(self):
        _, ranked = finder.find(FakeClient(), "Mirpur 10")
        self.assertEqual(ranked[0].phone, "+880 2 0000000")

    def test_haversine(self):
        # Dhaka Zero Point to Shahbag is roughly 1.6 km
        d = finder.haversine_m(90.4125, 23.7270, 90.3958, 23.7380)
        self.assertTrue(1500 < d < 2300, d)

    def test_city_level_fallback_is_flagged(self):
        class CityOnly(FakeClient):
            def geocode(self, text):
                return {"lon": 90.41, "lat": 23.81, "formatted": "Dhaka, DH, Bangladesh",
                        "rank": {"match_type": "match_by_city_or_disrict"}}
        origin, _ = finder.find(CityOnly(), "Dhanmondi 27, Dhaka")
        self.assertTrue(origin.coarse)
        origin, _ = finder.find(FakeClient(), "Mirpur 10")
        self.assertFalse(origin.coarse)

    def test_non_emergency_names_flagged(self):
        hosp = ["healthcare", "healthcare.hospital"]
        mk = lambda name, cats=hosp: finder.Facility(name, "", 0, 0, 0, categories=cats)  # noqa: E731
        self.assertTrue(mk("Al Fateh Diagnostics").maybe_not_er)
        self.assertTrue(mk("Ahammed Pharma").maybe_not_er)
        self.assertTrue(mk("Ispahani Islamia Eye Institute and Hospital").maybe_not_er)
        self.assertFalse(mk("Shahbagh P.G. Hospital").maybe_not_er)
        self.assertFalse(mk("Ahammed Pharma", ["healthcare", "healthcare.pharmacy"]).maybe_not_er)

    def test_polygon_area(self):
        self.assertAlmostEqual(finder.polygon_area_m2(square(90.4, 23.8, 100)), 10000, delta=50)
        self.assertIsNone(finder.polygon_area_m2({"type": "Point", "coordinates": [90.4, 23.8]}))
        multi = {"type": "MultiPolygon",
                 "coordinates": [square(90.4, 23.8, 10)["coordinates"],
                                 square(90.5, 23.8, 10)["coordinates"]]}
        self.assertAlmostEqual(finder.polygon_area_m2(multi), 200, delta=2)

    def test_worship_sizes_prefer_own_outline(self):
        _, ranked = finder.find(FakeClient(), "Mirpur 10", kind="worship", top=5)
        by_id = {f.place_id: f for f in ranked}
        self.assertAlmostEqual(by_id["small-mosque"].area_m2, 400, delta=5)
        self.assertEqual(by_id["small-mosque"].area_source, finder.SIZE_OWN)
        self.assertAlmostEqual(by_id["market-mosque"].area_m2, 2500, delta=20)
        self.assertEqual(by_id["market-mosque"].area_source, finder.SIZE_HOST)
        self.assertIsNone(by_id["no-outline"].area_m2)
        self.assertEqual(by_id["temple"].religion, "hinduism")

    def test_worship_sort_by_size(self):
        _, ranked = finder.find(FakeClient(), "Mirpur 10", kind="worship", sort="size", top=3)
        self.assertEqual([f.place_id for f in ranked], ["market-mosque", "temple", "small-mosque"])

    def test_religion_filter_category(self):
        client = FakeClient()
        finder.find(client, "Mirpur 10", kind="worship", religion="islam")
        self.assertIn(("places", ("religion.place_of_worship.islam",), 2000), client.calls)

    def test_worship_map_has_no_emergency_banner(self):
        client = FakeClient()
        origin, ranked = finder.find(client, "Mirpur 10", kind="worship")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.html")
            write_map(path, origin, ranked, None, "test-key", emergency=False)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        self.assertNotIn("Call <b>999</b>", text)
        self.assertIn('"area_approx": true', text)

    def test_map_written(self):
        client = FakeClient()
        origin, ranked = finder.find(client, "Mirpur 10")
        route = client.route((origin.lon, origin.lat), (ranked[0].lon, ranked[0].lat))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.html")
            write_map(path, origin, ranked, route, "test-key", title="<script>x</script>")
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        self.assertIn("B Hospital", text)
        self.assertIn("999", text)
        self.assertNotIn("<script>x</script>", text)


if __name__ == "__main__":
    unittest.main()
