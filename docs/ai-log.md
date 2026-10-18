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

Not yet verified against the live API (needs a key): response field names for Places
`contact`, and whether `traffic=approximated` is accepted for `motorcycle` in Route Matrix.

## Feedback ideas for Geoapify (to confirm during the benchmark)
- Mixed coordinate order across APIs (`lat,lon` vs `lon,lat`) is a frequent AI mistake. A short
  "coordinate order" note at the top of each spec would help.
- Local travel modes for South Asia (CNG / auto-rickshaw).
- Bangla-script geocoding quality.
