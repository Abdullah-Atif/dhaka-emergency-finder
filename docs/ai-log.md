# AI development log

What the AI coding agent did, what it got right, and where a human had to step in.

Tool: Claude Code. Inputs: the Geoapify OpenAPI JSON specifications for Forward Geocoding,
Places, Route Matrix and Routing, plus the Geoapify MCP documentation.

## 2026-10-18: prototype

**Prompt summary:** see [prompts/01-prototype.md](../prompts/01-prototype.md).

What worked:
- The agent read the specs and used the right servers: `/v1` for geocoding, routing and
  route matrix, `/v2` for places.
- It picked the exact category keys from the Places spec (`healthcare.hospital`,
  `service.fire_station`, `emergency.ambulance_station`, ...).
- It used the `x-api-key` header (documented in the specs' `securitySchemes`) instead of
  putting the key in the URL.
- It noticed from the spec that `traffic` only applies to motorized modes.

Points that needed care:
- **Coordinate order.** The Routing API `waypoints` use `lat,lon`, while the Places `filter` /
  `bias` and the Route Matrix `location` use `lon,lat`. This is the easiest place to make a
  mistake. It is now handled in one place (`geoapify.py`) with a comment.
- The places `filter=circle:` radius has to be widened when there are few results.
  This was a design choice, not something the spec suggests.
- Phone numbers are not in one fixed field. The code checks `contact.phone`, then
  `datasource.raw.phone` and `contact:phone`.

## 2026-10-18: first live run (free API key)

All four live checks worked on the first try. The agent-written client needed no fixes.
`traffic=approximated` is accepted for `drive` and `motorcycle`, and phone numbers come through.

| Input | Type / mode | Result | Observation |
|---|---|---|---|
| `Mirpur 10, Dhaka` | hospital / drive | 5 results, 2 to 5 min | The closest on the map (a government dispensary) was **not** the fastest to reach. Several "hospitals" are diagnostic centres or an eye hospital: OSM tagging, not a Geoapify bug. |
| `ধানমন্ডি ২৭` (Bangla) | pharmacy / drive | 3 results, 1 to 2 min | Bangla script with Bangla digits geocoded correctly to the Dhanmondi 27 (new Road 16) junction. |
| `23.7266, 90.3925` | fire / motorcycle | Lalbagh Fire Station, 8 min | Result #3 is a *mosque inside the Fire Service HQ* tagged as a fire station: data-quality issue. Road distance is 2× the straight line (old Dhaka streets). |
| `Uttara Sector 7, Dhaka` | police / drive (JSON) | Uttara Thana, 46 s | The sector name geocoded to the nearest highway, not the sector centre: coarse result for informal sector names. |

Ideas for the benchmark:
- Filter or flag places whose name suggests a non-emergency facility ("Diagnostic", "Eye", "Mosque").
- Record geocoding precision (`result_type`) for sector or road-number style addresses.

## Feedback ideas for Geoapify (to confirm during the benchmark)
- Mixed coordinate order across APIs (`lat,lon` vs `lon,lat`) is a frequent AI mistake. A short
  "coordinate order" note at the top of each spec would help.
- Local travel modes for South Asia (CNG / auto-rickshaw).
- Bangla-script geocoding quality.
