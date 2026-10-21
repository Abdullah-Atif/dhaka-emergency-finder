# Session 02: "আমি ফার্মগেটে আছি, গাড়িতে সবচেয়ে তাড়াতাড়ি কোন হাসপাতালে যেতে পারব?"

("I am at Farmgate. Which hospital can I reach fastest by car?", asked in Bangla.)

- **Date:** 2026-10-21
- **Client:** Claude Code 2.1.283, using its **built-in MCP client** (`claude -p` with an MCP config for
  `https://api.geoapify.com/v1/mcp`, `x-api-key` header). The only tools allowed were the Geoapify MCP tools.
- **Agent instructions:** [AGENT_INSTRUCTIONS.md](../AGENT_INSTRUCTIONS.md), as they were before this session
- **Full transcript (tool calls, arguments, results, final answer):** [02-farmgate-claude-code-bangla.jsonl](02-farmgate-claude-code-bangla.jsonl)
- 6 turns, 35 seconds

## Tool calls

| # | Tool | Key arguments | Outcome |
|---|---|---|---|
| 1 | `geocode_address` | `"Farmgate, Dhaka, Bangladesh"`, `country_codes: ["bd"]` | Farmgate Bus Stop (23.7573, 90.3901), `match_type` = `inner_part`, confidence 1 |
| 2 | `search_places` | `healthcare.hospital`, 2 km, limit 15 | 15 hospital-tagged places |
| 3 | `calculate_route_matrix` | 1 source × 10 targets, `drive` (**no `traffic`**) | 19 s to 221 s |
| 4 | `calculate_route` | to Al Razi Hospital Complex, `include_instructions: true` | 401 m, 35 s, 3 steps |

Session 01 used `geometry_scope: "steps"` without `include_instructions`. This time the agent set both correctly
on the first try.

## Final answer (Bangla, abridged)

> **জরুরি অবস্থা? ৯৯৯-এ কল করুন।** … যানজট ধরা হয়নি, তাই আসল সময় আরও বেশি লাগবে।
>
> **সাধারণ হাসপাতাল (দ্রুততম ৩টি):** 1. Al Razi Hospital Complex: প্রায় ১ মিনিট, ৪০১ মিটার, খোলা থাকে ২৪/৭ ·
> 2. Samorita Hospital: প্রায় ২ মিনিট, ১.৪ কিমি · 3. SIBL Foundation Hospital: প্রায় ২ মিনিট, ২.০ কিমি
>
> (Square Hospitals সোজাসুজি দূরত্বে কাছে মনে হলেও গাড়িতে বেশি সময় লাগে।)
>
> **আরও কাছে কিছু জায়গা আছে, তবে সেগুলো সাধারণ হাসপাতাল না-ও হতে পারে:** Brain and Mind Hospital, Al Fateh
> Diagnostics, Ispahani Islamia Eye Institute and Hospital …

The full answer, with the route in 3 steps, is the last line of the transcript.

## What worked
- **Bangla in, Bangla out.** The agent understood the question and answered in Bangla, keeping facility names as
  returned by the tools.
- **It separated likely non-emergency places on its own.** The instructions only ask for a general reminder that a
  place may not have an emergency department. The agent went further and put Al Fateh Diagnostics, the Ispahani Islamia Eye
  Institute and Brain and Mind Hospital in a separate "may not be a general hospital" list, judging by their names.
  Our CLI does the same with a name heuristic.
- **It did not invent data.** "Open 24/7" comes from the place's `opening_hours` field in the `search_places` result,
  and missing phone numbers are reported as "not listed".
- **It pointed out the map-vs-road difference** (Square Hospitals looks closer but takes longer).

## What needed correction
- **No `traffic` on the matrix.** The instructions said to rank by travel time but did not say to use
  `traffic: "approximated"`, so the agent used free-flow speeds. It did tell the user honestly that traffic was not
  counted. The instructions now require `traffic: "approximated"` for `drive` and `motorcycle`.
- `search_places` was called with `limit: 15`, not 10 as the instructions suggest. The agent then sent the 10 closest
  places to the matrix, which is fine.
