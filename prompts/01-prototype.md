# Prompt 01: prototype CLI

This is a summary of the task brief the Claude Code session worked from. The session read these spec files:
- https://apidocs.geoapify.com/assets/openapi/specs/forward-geocoding/forward-geocoding-api-openapi-specs.json
- https://apidocs.geoapify.com/assets/openapi/specs/places/places-api-openapi-specs.json
- https://apidocs.geoapify.com/assets/openapi/specs/route-matrix/route-matrix-api-openapi-specs.json
- https://apidocs.geoapify.com/assets/openapi/specs/routing/routing-api-openapi-specs.json

---

> Using only the attached Geoapify OpenAPI specifications, build a Python 3.9+ command line
> tool with **no third-party dependencies** (standard library only) that finds the
> fastest-to-reach emergency facility in Dhaka.
>
> - Input: free text (English or Bangla) or "lat,lon".
> - Geocode with the Forward Geocoding API, restricted to Bangladesh and biased to Dhaka.
> - Search with the Places API around the location. Support hospital, clinic, pharmacy,
>   police, fire station and ambulance station, using exact category keys from the spec.
>   Widen the radius (2 → 5 → 10 km) when there are fewer than 5 results.
> - Rank up to 10 candidates by travel time with the Route Matrix API (one source, many targets).
>   Use `traffic=approximated` for motorized modes.
> - Optional: get the route to #1 with the Routing API and write an HTML map (Leaflet + Geoapify tiles).
> - Always print "Call 999 first". Never invent data.
> - Authenticate with the header from the spec's securitySchemes. Read the key from
>   GEOAPIFY_API_KEY.
> - Add unit tests with a fake client, so they run without a key.
> - Be careful about latitude/longitude order: check each API's spec.

## Design decisions made in the session
- All HTTP calls live in one module (`geoapify.py`), so that the coordinate order is handled in a single place.
- The map title is HTML-escaped, and a test checks this.

## Corrections
_None yet. Record each human correction here as it happens, with the reason._
