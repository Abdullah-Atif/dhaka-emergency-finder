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

## 2026-10-18: second feature, places of worship and their size

Request: show nearby mosques and how big each one is, and do the same for every religion.

What was checked against the live API before writing code:
- The Places spec has `religion.place_of_worship` with subcategories `islam`, `hinduism`,
  `christianity`, `buddhism`, `sikhism`, `judaism`, `multifaith`, `shinto`.
- The live MCP `search_places` call returns **points only** (name, address, distance, place_id).
  There is no MCP tool for place details or building outlines. So an MCP-only agent cannot measure a
  place's size. The first MCP call also failed because the argument is `radius_meters`, not `radius`.
  The MCP server's error (`"radius" is not allowed`) was clear enough to fix it straight away.
- The Place Details API (`features=details,building`) returns the place's own outline (`details`)
  and/or the building that contains it (`building`). The area comes from the polygon.

Live results:

| Query | Result | Observation |
|---|---|---|
| Mirpur 10, mosques | 4 mosques, 1 to 2 min | 1 own outline (949 m²), 1 only a containing building (≤ 329 m²), 2 with no outline. Earlier test: "Shah Ali Plaza Market Masjid" got 2,083 m², which is the whole market building. This is why the containing building is shown as an upper bound. |
| Dhakeshwari Temple, `--sort size` | Dhakeshwari National Temple 7,902 m², then smaller shrines | 7,902 m² is the **compound** outline, not one building, so the label "mapped outline" is used instead of "floor area". Unnamed shrines first showed the street name as their name (`address_line1` fallback); this was fixed. |
| "BUET, Dhaka" | Geocoded to "BUET-TPHS Building" in Gulshan | Wrong: the BUET campus is in Palashi. Landmark and abbreviation geocoding is a benchmark item and feedback for Geoapify. |

No `capacity` or `building:levels` tags were found on any mosque tested, so the size is an area, not a headcount.

Ideas for the benchmark:
- Filter or flag places whose name suggests a non-emergency facility ("Diagnostic", "Eye", "Mosque").
- Record geocoding precision (`result_type`) for sector or road-number style addresses.

## Feedback ideas for Geoapify (to confirm during the benchmark)
- Mixed coordinate order across APIs (`lat,lon` vs `lon,lat`) is a frequent AI mistake. A short
  "coordinate order" note at the top of each spec would help.
- Local travel modes for South Asia (CNG / auto-rickshaw).
- Bangla-script geocoding quality.
- An MCP tool for place details or outlines (or a `geometry` option on `search_places`), so agents can
  answer "how big is it?" with `measure_geometry` alone.
