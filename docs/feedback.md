# Feedback for Geoapify: OpenAPI specifications and MCP tools

Collected while building Dhaka Emergency Finder (October 2026). Every point below comes from a live call that is
recorded in this repository: [benchmark](../benchmark/), [manual review](../benchmark/NOTES.md),
[agent session](../agent/sessions/01-mirpur-hospital.md), [AI log](ai-log.md).

## What worked well

- **The OpenAPI specs were enough to write a working client.** An AI coding agent (Claude Code) wrote the
  geocoding → places → route matrix → routing client from the four JSON specs alone. The first live run worked
  without fixes: right servers (`/v1` vs `/v2`), exact category keys, and the `x-api-key` header from
  `securitySchemes`.
- **MCP tools use named `{lat, lon}` objects.** This removes the coordinate-order bug class completely (see
  OpenAPI #1 below).
- **MCP error messages are precise.** `"radius" is not allowed` and
  `geometry_scope "steps" requires include_instructions to be true` were each fixed by the agent in one retry.
- **Route Matrix with `traffic=approximated`** answers the core question of the project in one request.
- **Bangla input works well.** All 4 Bangla-script queries in the benchmark geocoded correctly, including Bangla digits.

## OpenAPI specifications / REST APIs

1. **Coordinate order differs between APIs.** Routing `waypoints` are `lat,lon`, while Places `filter`/`bias` and
   Route Matrix `location` are `lon,lat`. This is the most likely bug in AI-generated code.
   *Suggestion:* a one-line "coordinate order" note at the top of each spec's description, and examples that
   use the same point everywhere.
2. **Wrong places returned as `full_match`.** "Gulshan Circle 1, Dhaka" → Gulshan **2** Circle;
   "Shapla Chattar, Motijheel, Dhaka" → a place in Khilkhet (about 15 km away); "Bangladesh University of
   Engineering and Technology" → "Polygon Technology Ltd." All three had `match_type: full_match`, so a
   client cannot detect them.
   *Suggestion:* penalise matches on a single generic token ("Technology", "Old", "BUET") for landmark queries.
3. **Silent city-level fallback.** "Dhanmondi 27, Dhaka" returns the whole city (`result_type: city`,
   `match_type: match_by_city_or_disrict`, confidence 0.5) as the only result. It looks like a normal answer.
   *Suggestion:* document this case prominently in the Forward Geocoding spec ("check `rank.match_type` before
   using the result").
4. **Typo in an enum value:** `match_by_city_or_disrict` (should be "district"). Clients have to match the
   misspelling. Fixing it now would need a compatibility alias.
5. **Local abbreviations are not understood.** "Bashundhara R/A Block D" is not found at all, while
   "Bashundhara Residential Area" works. `R/A` (Residential Area) is very common in Dhaka addresses.
6. **No way to filter hospitals by emergency capability.** In 3 of 9 benchmark locations the fastest
   `healthcare.hospital` is, by its name, a diagnostic centre or an eye hospital. There is no Places *condition*
   for OpenStreetMap `emergency=yes`, and `emergency.emergency_ward_entrance` returned 0 results within 15 km of
   central Dhaka. *Suggestion:* expose `emergency=yes/no` on hospitals as a condition (for example
   `emergency_department.yes`).
7. **Near-duplicate places.** "radda" and "RADDA" (about 5 m apart) are both returned for Mirpur 10.

## MCP tools

1. **No outline or place-details tool.** `search_places` returns points only (one result had
   `building: {"type": "mosque"}`, but no geometry), so `measure_geometry` has nothing to measure. An agent cannot
   answer "how big is this place?" with MCP alone. The REST Place Details API can.
   *Suggestion:* a `get_place_details` tool, or an optional `include_geometry` on `search_places`.
2. **`traffic` defaults to `free_flow` on both `calculate_route_matrix` and `calculate_route`.** The agent passed
   `approximated` to the matrix but forgot it on the route, and got 33 s vs. 120 s for the same trip.
   *Suggestion:* mention in both tool descriptions that the matrix and route calls should share `mode` and `traffic`.
3. **`geometry_scope: "steps"` silently depends on `include_instructions`.** The error is clear, but the
   dependency could be expressed in the schema description, or `include_instructions` could default to true
   when `steps` is requested.
4. **`geocode_address` returns `rank.match_type` and `confidence`.** This is good. The tool description could tell
   agents to check them before using the result, because a city-level fallback otherwise looks like a valid
   answer (see OpenAPI #3).
