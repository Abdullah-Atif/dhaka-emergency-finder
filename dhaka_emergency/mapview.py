"""Write a self-contained HTML map (Leaflet + Geoapify map tiles)."""

import html
import json

from .finder import SIZE_HOST

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dhaka Emergency Finder</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  html, body {{ margin: 0; height: 100%; font-family: system-ui, sans-serif; }}
  #map {{ position: absolute; inset: 0; }}
  .banner {{ position: absolute; z-index: 1000; top: 10px; left: 50px; right: 10px;
            background: #b00020; color: #fff; padding: 8px 12px; border-radius: 6px; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="banner" style="background: {banner_bg}">{banner}{title}</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const data = {data};
const map = L.map('map');
L.tileLayer('https://maps.geoapify.com/v1/tile/osm-bright/{{z}}/{{x}}/{{y}}.png?apiKey={key}', {{
  maxZoom: 20,
  attribution: 'Powered by <a href="https://www.geoapify.com/">Geoapify</a> | &copy; OpenStreetMap contributors'
}}).addTo(map);
const bounds = [[data.origin.lat, data.origin.lon]];
L.circleMarker([data.origin.lat, data.origin.lon], {{radius: 9, color: '#1565c0', fillOpacity: 0.9}})
  .addTo(map).bindPopup('You: ' + data.origin.label);
data.places.forEach((p, i) => {{
  bounds.push([p.lat, p.lon]);
  const mins = p.time_s == null ? 'no route' : Math.round(p.time_s / 60) + ' min';
  L.marker([p.lat, p.lon]).addTo(map)
    .bindPopup('<b>#' + (i + 1) + ' ' + p.name + '</b><br>' + mins
      + (p.area_m2 ? '<br>' + (p.area_approx ? '&le; ' : '') + Math.round(p.area_m2) + ' m²' : '')
      + '<br>' + p.address + (p.phone ? '<br>' + p.phone : ''));
}});
if (data.route) {{
  const layer = L.geoJSON(data.route, {{style: {{color: '#b00020', weight: 5}}}}).addTo(map);
  map.fitBounds(layer.getBounds().extend(L.latLngBounds(bounds)), {{padding: [40, 40]}});
}} else {{
  map.fitBounds(bounds, {{padding: [40, 40]}});
}}
</script>
</body>
</html>
"""


def write_map(path, origin, facilities, route_feature, api_key, title="", emergency=True):
    data = {
        "origin": {"lon": origin.lon, "lat": origin.lat, "label": origin.label},
        "places": [
            {
                "name": f.name,
                "address": f.address,
                "phone": f.phone,
                "lon": f.lon,
                "lat": f.lat,
                "time_s": f.drive_s,
                "area_m2": f.area_m2,
                "area_approx": f.area_source == SIZE_HOST,
            }
            for f in facilities
        ],
        "route": route_feature,
    }
    page = TEMPLATE.format(
        data=json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        key=api_key,
        title=html.escape(title),
        banner="Emergency? Call <b>999</b> first. " if emergency else "",
        banner_bg="#b00020" if emergency else "#2e5d8a",
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
