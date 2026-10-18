"""Minimal Geoapify REST client (standard library only).

Endpoints and parameters follow the Geoapify OpenAPI specifications:
https://apidocs.geoapify.com/open-api/
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE_V1 = "https://api.geoapify.com/v1"
BASE_V2 = "https://api.geoapify.com/v2"

# Rough centre of Dhaka, used to bias geocoding results (lon, lat).
DHAKA_CENTER = (90.4125, 23.8103)


class GeoapifyError(RuntimeError):
    pass


class GeoapifyClient:
    def __init__(self, api_key=None, timeout=20):
        self.api_key = api_key or os.environ.get("GEOAPIFY_API_KEY")
        if not self.api_key:
            raise GeoapifyError(
                "No API key. Set the GEOAPIFY_API_KEY environment variable "
                "(get a free key at https://myprojects.geoapify.com)."
            )
        self.timeout = timeout

    def _request(self, url, params=None, body=None):
        query = urllib.parse.urlencode(params or {}, safe=",:|")
        if query:
            url = f"{url}?{query}"
        headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise GeoapifyError(f"HTTP {e.code} from {url.split('?')[0]}: {detail}") from e
        except urllib.error.URLError as e:
            raise GeoapifyError(f"Network error: {e.reason}") from e

    def geocode(self, text, country="bd", bias=DHAKA_CENTER, lang="en"):
        """Forward geocoding. Returns the best result dict or None."""
        params = {
            "text": text,
            "filter": f"countrycode:{country}",
            "bias": f"proximity:{bias[0]},{bias[1]}",
            "lang": lang,
            "limit": 1,
            "format": "json",
        }
        results = self._request(f"{BASE_V1}/geocode/search", params).get("results", [])
        return results[0] if results else None

    def places(self, lon, lat, categories, radius_m, limit=20, lang="en"):
        """Places API. Returns a list of GeoJSON features."""
        params = {
            "categories": ",".join(categories),
            "filter": f"circle:{lon},{lat},{radius_m}",
            "bias": f"proximity:{lon},{lat}",
            "limit": limit,
            "lang": lang,
        }
        return self._request(f"{BASE_V2}/places", params).get("features", [])

    def route_matrix(self, source, targets, mode="drive", traffic="approximated"):
        """Route Matrix API with one source. source/targets are (lon, lat).

        Returns a list of {"distance", "time"} dicts (None when unreachable),
        one per target, in the same order.
        """
        body = {
            "mode": mode,
            "sources": [{"location": list(source)}],
            "targets": [{"location": list(t)} for t in targets],
        }
        if mode not in ("walk", "hike", "bicycle", "mountain_bike", "road_bike"):
            body["traffic"] = traffic
        data = self._request(f"{BASE_V1}/routematrix", body=body)
        row = data.get("sources_to_targets", [[]])[0]
        out = [None] * len(targets)
        for cell in row:
            if cell.get("time") is not None and cell.get("distance") is not None:
                out[cell["target_index"]] = {"distance": cell["distance"], "time": cell["time"]}
        return out

    def route(self, start, end, mode="drive", traffic="approximated"):
        """Routing API between two (lon, lat) points. Returns a GeoJSON feature."""
        params = {
            # The Routing API expects lat,lon for waypoints.
            "waypoints": f"{start[1]},{start[0]}|{end[1]},{end[0]}",
            "mode": mode,
            "format": "geojson",
        }
        if mode not in ("walk", "hike", "bicycle", "mountain_bike", "road_bike"):
            params["traffic"] = traffic
        features = self._request(f"{BASE_V1}/routing", params).get("features", [])
        return features[0] if features else None
