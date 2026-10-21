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


def feature(name, lon, lat, phone=None):
    props = {"name": name, "lon": lon, "lat": lat, "address_line2": f"{name} road, Dhaka"}
    if phone:
        props["datasource"] = {"raw": {"phone": phone}}
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Point", "coordinates": [lon, lat]}}


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
        def facility(name, cats=("healthcare", "healthcare.hospital")):
            feat = {"properties": {"name": name, "lon": 90.4, "lat": 23.8, "categories": list(cats)}}
            return finder._to_facility(feat, finder.Origin(90.4, 23.8, "x"))
        self.assertTrue(facility("Al Fateh Diagnostics").maybe_not_er)
        self.assertTrue(facility("Ispahani Islamia Eye Institute and Hospital").maybe_not_er)
        self.assertFalse(facility("Shahbagh P.G. Hospital").maybe_not_er)   # confirmed (BMU)
        self.assertIsNone(facility("Ahammed Pharma", ["commercial.chemist"]).cls)  # not a hospital search

    def test_non_emergency_places_go_last(self):
        class Mixed(FakeClient):
            def places(self, lon, lat, categories, radius_m, limit=20):
                fs = [feature("Al Fateh Diagnostics", 90.3660, 23.8075), feature("B Hospital", 90.3700, 23.8100),
                      feature("C Hospital", 90.3800, 23.8200), feature("D Hospital", 90.3900, 23.8300),
                      feature("E Hospital", 90.4000, 23.8400)]
                for f in fs:
                    f["properties"]["categories"] = ["healthcare", "healthcare.hospital"]
                return fs
            def route_matrix(self, source, targets, mode="drive"):
                return [{"distance": 100, "time": 60 if lon == 90.3660 else 600} for lon, _lat in targets]
        _, ranked = finder.find(Mixed(), "Mirpur 10")
        self.assertEqual(ranked[-1].name, "Al Fateh Diagnostics")   # fastest, but not an emergency facility

    def test_dedupe_dmch_point_and_campus(self):
        mk = lambda n, lat, lon: finder.Facility(n, "", lon, lat, 0)  # noqa: E731
        out = finder.dedupe([
            mk("Dhaka Medical College Hospital, Government hospital, Secretariat Rd, Dhaka", 23.7259, 90.3973),
            mk("Dhaka Medical College Hospital", 23.7255, 90.3978),
            mk("Burn & Plastic Surgery Unit, Dhaka Medical College Hospital, Dhaka", 23.7257, 90.3980),
            mk("radda", 23.80756, 90.36969), mk("RADDA", 23.80755, 90.36976),
            mk("(unnamed) · Road 1", 23.70, 90.40), mk("(unnamed) · Road 1", 23.70, 90.40),
        ])
        self.assertEqual([f.name for f in out], ["Dhaka Medical College Hospital",
                                                 "Burn & Plastic Surgery Unit, Dhaka Medical College Hospital, Dhaka",
                                                 "radda", "(unnamed) · Road 1", "(unnamed) · Road 1"])

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
