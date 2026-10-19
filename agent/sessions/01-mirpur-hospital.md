# Session 01: "Fastest hospital from Mirpur 10 golchottor by car?"

- **Date:** 2026-10-19
- **Agent:** Claude Code (Claude Opus 5.5), following [AGENT_INSTRUCTIONS.md](../AGENT_INSTRUCTIONS.md)
- **How the tools were called:** Geoapify MCP over JSON-RPC with [`agent/mcp_call.py`](../mcp_call.py). The agent
  decided every call itself. The helper only sends the request and logs it.
- **Full transcript (all 6 calls, arguments and results):** [01-mirpur-hospital.jsonl](01-mirpur-hospital.jsonl)

## Tool calls

| # | Tool | Key arguments | Outcome |
|---|---|---|---|
| 1 | `geocode_address` | `"Mirpur 10 golchottor, Dhaka, Bangladesh"` | Mirpur 10 Bus Station (23.8074, 90.3682), `match_type` = `inner_part`, confidence 1 |
| 2 | `search_places` | `healthcare.hospital`, 2 km, limit 10 | 10 places within 75 to 201 m (straight line) |
| 3 | `calculate_route_matrix` | 1 source × 10 targets, `drive`, `traffic=approximated` | Times 120 s to 429 s |
| 4 | `calculate_route` | to #1, `geometry_scope=steps` | **Error:** `geometry_scope "steps" requires include_instructions to be true` |
| 5 | `calculate_route` | same + `include_instructions=true` | 254 m, **33 s**. The agent forgot `traffic`, so this does not match the matrix (120 s). |
| 6 | `calculate_route` | `traffic=approximated`, `geometry_scope=none` | 254 m, **121 s**. This now matches the matrix. |

## Final answer given by the agent

> **Emergency? Call 999 (Bangladesh national emergency service).**
>
> From Mirpur 10 golchottor, fastest by car (estimated traffic):
> 1. **AALOK HEALTHCARE**: about 2 min, 254 m by road. Phone not listed.
> 2. **FSCD Burn Unite Hospital**: about 2 min, 220 m by road. Phone not listed.
> 3. **DR. AZMAL HOSPITAL LTD.**: about 2 min, 278 m by road. Phone not listed.
>
> Note: **Medinova Hospital** looks very close on the map (122 m), but by road it is about 1 km and 7 min away.
>
> Route to #1: drive north on Begum Rokeya Sarani (বেগম রোকেয়া সরণী), turn left onto Road No. 9; the destination is on the left.
>
> Map data may be incomplete. A listed place may not have an emergency department. For example, "Aalok
> Diagnostic Center" and "Radda MCH-FP Centre" are tagged as hospitals.

## What worked
- Every MCP tool accepted `{lat, lon}` objects. This avoided the lat/lon order problem of the REST APIs
  (where Routing uses `lat,lon` but Places and Route Matrix use `lon,lat`).
- `geocode_address` returns `rank.match_type` and `confidence`, so an agent *can* detect weak matches.
- The error in call 4 was clear enough to fix in one retry.

## What needed correction
- **Calls 4 and 5 were agent mistakes.** `geometry_scope=steps` needs `include_instructions`, and `traffic` must be
  passed again to `calculate_route`, or route and matrix times disagree (33 s vs 120 s). The agent
  instructions now say "use the same `mode` and `traffic` for the matrix and the route".
- `search_places` returned near-duplicates ("radda" and "RADDA", 5 m apart). The agent should merge
  places with the same name within about 20 m.
