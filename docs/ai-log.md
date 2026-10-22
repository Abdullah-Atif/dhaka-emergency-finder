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

> **Update 2026-10-21:** at Geoapify's request, the agreed Batch #2 scope is emergency facilities only, so this
> feature was removed from `main`. The code, tests and the recorded mosque session are kept on the branch
> [`feature/places-of-worship`](https://github.com/Abdullah-Atif/dhaka-emergency-finder/tree/feature/places-of-worship).
> The findings below still count as feedback: the MCP `search_places` tool returns points only.

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

## 2026-10-19: benchmark and first recorded agent sessions

- Wrote and ran `benchmark/run.py` (20 locations). Results: [benchmark/results.md](../benchmark/results.md),
  manual review: [benchmark/NOTES.md](../benchmark/NOTES.md).
- The benchmark exposed a **silent bug in our own CLI**. When geocoding fell back to the whole city ("Dhanmondi 27,
  Dhaka" → "Dhaka"), the tool listed hospitals around the city centre without any warning. Fix: read
  `rank.match_type` and warn on `match_by_city_or_disrict`. A test was added.
- It also showed that 6 of 16 "fastest hospitals" are diagnostic centres, pharmacies and similar. A name-based flag was added.
- Recorded two agent sessions in which Claude Code called Geoapify MCP tools itself
  ([agent/sessions/](../agent/sessions/)). The agent made two mistakes there, which are kept in the transcript:
  `geometry_scope=steps` without `include_instructions`, and forgetting `traffic` on `calculate_route`, which
  made route and matrix times disagree. The agent instructions were updated after each one.

## 2026-10-21: scope agreed with Geoapify

Geoapify selected the project for Batch #2 (deadline 2026-11-15) and asked for a smaller first version:
emergency facilities only, and a 10-location benchmark.

- The places-of-worship feature was moved to the branch `feature/places-of-worship` and removed from `main`
  (code, tests, docs, and the mosque agent session).
- The benchmark set was cut from 20 to 10 locations. It keeps the English/Bangla pairs for the same places
  and the problem cases. Re-run result: map-nearest ≠ fastest in 8 / 9 (at least 1 min faster in 6 / 9);
  geocoding 8 / 10 (Bangla 4 / 4). The 20-location run stays in the git history (commit `3392669`).
- A "saves at least 1 minute" line was added to the summary, so that a 0.1-minute difference is not counted
  as a meaningful one.

## 2026-10-21: agent session inside Claude Code (Bangla)

- Ran a full session with Claude Code's built-in MCP client (`claude -p`, only Geoapify tools allowed), asked in Bangla
  about Farmgate: [agent/sessions/02-farmgate-claude-code-bangla.md](../agent/sessions/02-farmgate-claude-code-bangla.md).
- It answered correctly in Bangla, used `include_instructions` properly, and on its own grouped diagnostic or eye
  hospitals as "may not be a general hospital".
- Gap found: the matrix call had no `traffic`, because the instructions never required it. The agent disclosed that
  traffic was not counted. The instructions now require `traffic: "approximated"` for `drive` and `motorcycle`.
- Session 01 is now labelled clearly in the tutorial as using the JSON-RPC helper `agent/mcp_call.py`.

## 2026-10-21: VS Code + GitHub Copilot session

- Tested the agent in VS Code 1.142 + Copilot Chat 0.70 (Agent mode, Auto model → `gpt-6-luna`):
  [agent/sessions/03-mirpur-vscode-copilot.md](../agent/sessions/03-mirpur-vscode-copilot.md). It gave the same answer as
  Claude Code in session 01 and used `traffic: "approximated"` on both calls.
- **Mistake (mine):** to save time I wrote the Geoapify key directly into the local, git-ignored `.vscode/mcp.json`.
  The Copilot agent read that file by itself, after a permission prompt, and so sent the key to the model. The local
  file now uses the `${input:geoapify-key}` prompt from `agent/vscode-mcp.example.json`, and the setup guide warns
  against inline keys. The key must be replaced.
- VS Code quirk: pressing Start before the first chat message fails with "Send a message first."

## 2026-10-21: web app for the €500 "best app" bonus

- Added `docs/app/`: a single static page (Leaflet + Geoapify REST from the browser) with a tap-to-call 999 button,
  "use my location", Bangla/English, map + route, and the same warnings as the CLI. Pure helpers tested with
  `node --test tests/app.test.js`.
- First live run felt slow: about 13 s before any result. Timing each call once (one sample, home connection in
  Dhaka): geocode 3.9 s, places 2.3 s, route matrix (`traffic=approximated`) 7.4 s. Changes: one 10 km Places call
  instead of widening 2 → 5 → 10 km (in Mirpur the 2 km and 10 km calls returned the same 10 places); show the nearest
  places by distance as soon as Places answers, then re-sort by travel time; with GPS, search first and fetch the
  address label in parallel. Next run: first results 1.6 s, final ranking 2.1 s (the network was also faster then).
- Two data problems found while testing, both now handled in the app: duplicate places ("radda" and "RADDA", 5 m
  apart), and a mosque inside the Fire Service HQ returned as a fire station (`service.fire_station`).
- Mistake caught before shipping: the "different place" hint list had `quarter`, which would also have flagged
  "Fire Service & Civil Defence Headquarter". It was removed, and a test covers that case.

## 2026-10-22: demo key for the hosted web app

- Created a second free-plan key just for the web app and restricted it in the Geoapify project to Origin
  `^https://abdullah-atif\.github\.io$` and Referer `^https://abdullah-atif\.github\.io/`. Regex anchors matter:
  the dialog says a pattern can match *any part* of the origin, so a plain `https://abdullah-atif.github.io` would
  also match `https://abdullah-atif.github.io.evil.com`.
- Tested with curl: another site's Origin → 401; our Origin or Referer → 200; map tiles with our Referer → 200;
  **no Origin and no Referer → 200**. So the restriction stops other websites, but not scripts. Added to
  [feedback.md](feedback.md). The original key (used by the CLI and MCP setups) was left unrestricted, because
  command-line requests send no Origin.

## 2026-10-22: suggestions while typing

- User request: "like Google Maps, show suggestions while I type". Added Geoapify Address Autocomplete to the web app
  (300 ms debounce, minimum 3 characters, ignores stale responses, keyboard ↑/↓/Enter/Esc, ARIA combobox).
- Tested the API first: English partial words work well and quickly ("dhanmo" → 5 Dhanmondi places in about 0.6 s), but
  **partial Bangla words return nothing**, whatever the `lang` or filter. Fallback: Bangla text → `/geocode/search`.
  Verified in the browser: "dhanmo" → 5 suggestions, ↓ + Enter picks one and runs the search; "ধানমন্ডি" → 2
  suggestions through the fallback.

## 2026-10-22: "Why is Dhaka Medical College Hospital unnamed?"

- User report. I could not reproduce DMCH itself as unnamed, but the check found two real problems near it:
  (1) an **unnamed** hospital-tagged building right beside DMCH (OSM way 1478513844, address "Kazi Motaher hossain vaban").
  It was shown as "(unnamed)", which is easy to mistake for DMCH. It is now shown as "(unnamed) · Kazi Motaher hossain vaban".
  (2) DMCH appeared **twice**: a point with the address appended to its name, and the campus outline with a Bangla `name`
  and English `name:en`.
- Fixes in both the web app and the CLI: prefer `name:en` (the web app shows `name:bn` / Bangla `name` in the Bangla
  interface); merge duplicates when one name is the start of the other (12 or more characters) and they are less than
  300 m apart; never merge unnamed places. Tests added in both languages.

## 2026-10-22: "Searching BUET, why is Kazi Motaher Hossain first and not DMCH?"

- Not a ranking bug: from BUET Teachers' Quarter, DMCH is 338 m in a straight line but the car route is 874 m
  (Shaheed Minar Road → Sir Syed Road → into the campus), 7.8 min with `traffic=approximated`. The unnamed hospital-tagged
  building is 486 m / 5.5 min. DMCH ranked #7, and the app only showed 5 results.
- UX fixes: a "Show all N places" button (all candidates, with their map pins), and a warning on unnamed places
  ("may be a small clinic or office; check before going"). The ranking itself is unchanged: the app should not
  silently prefer places it *thinks* are bigger. The real fix needs data: an emergency-department tag (feedback #6).

## 2026-10-22: deep research and a name-based classifier

- User request: "the names say a lot, guess better from them" after seeing diagnostic centres and an unnamed
  building ranked as the fastest "hospital", with no information on size or departments.
- Measured first: of 447 `healthcare.hospital` places in Dhaka, no place has `beds`, 40 have `emergency`, and only a few
  percent have `healthcare:speciality`, `phone` or `opening_hours`. Size and departments cannot be shown from the data.
- Ran a deep-research pass with 4 parallel researchers + a writer (report: [research/hospital-classification.md](research/hospital-classification.md)):
  OSM tagging rules and Dhaka data problems; Bangladeshi naming and licensing (hospital/clinic/nursing home are one
  legal category; diagnostic centres are licensed separately); sources for 24-hour emergency departments (strongly
  confirmed for only 7); hotline status (999 active; fire service now 102; 16263 uncertain after a 2026 funding crisis).
- Built `docs/app/facility_rules.json` + `classify.js` (web app) and `dhaka_emergency/classify.py` (CLI) from it. They
  agree on all 837 hospital/clinic places in Dhaka and share 30 test cases.
- Evaluation ([benchmark/classify_eval.md](../benchmark/classify_eval.md)): 40-place random sample reviewed by hand:
  36/40 right, 4 fixed (a consultation centre with "hospital" in its name, the real name in the second comma part,
  "Orthopedic **and General** Hospital", the typo "Metarnity"). Because the fixes were made on that sample, I then
  checked a **fresh** sample of 30: 28/30 right, 2 left as "unknown" ("Mononiramoy", a mental-health centre: rule
  added afterwards; "DigiLab"). No dangerous error in either sample. In every disagreement with OSM's own
  `emergency` tag, the tag was the one that was wrong.
- App and CLI now show a badge per place (confirmed / government / not verified / specialised / not an emergency
  facility / unknown) and move "not an emergency facility" places to the end of the list.

## 2026-10-22: nearest major hospital

- User request: "shouldn't we also recommend the big hospitals with more services?"
- The map has no bed counts, so "major" = source-confirmed general 24h emergency, government general hospital, or
  medical college hospital (`major` in classify.js / classify.py, shared test cases).
- Measured first: the 100 nearest hospitals reach only ~4 km in central Dhaka and missed Suhrawardy (government,
  4.5 km from Mirpur 10); 200 reach ~6 km. Cost checked on geoapify.com/pricing-details: Places 1 credit + 1 per 20
  places, Route Matrix 1 per target, so ~27 credits per hospital search instead of ~13.
- Duplicate entries (Sohrawardy/Suhrawardi, three PG Hospital points) wasted the major slots. Distance alone could not
  merge them (BIRDEM is 80 m from PG Hospital), so they merge on the same confirmed hospital, or within 300 m with the
  same consonant key of the first name word.
- Web app: "Nearest major hospital" card + "Major hospitals only" switch (EN/BN). CLI: `--major` and a
  "Nearest major hospital" line. Agent instructions: same rule for MCP agents.

## 2026-10-22: agent test found a NITOR miss

- The user tested the agent (Claude Code, Bangla prompt, Mirpur 10, turn-by-turn route + nearest major hospital).
  The answer followed the instructions: 999 first, 3 hospitals by travel time, "not verified" badges, a 4-step route,
  nearest major hospital. The agent itself reported that `classify.py` labelled NITOR as a physio centre.
- Cause: NITOR has 5 map entries. "... Rehabilitation (NITOR)" did not match the confirmed alias because of the
  bracket, and "Traumtology" is a typo; both fell to the soft rule "rehabilitation → physio".
- Fix: the confirmed check now also tries the name without "(...)" and the text inside it (this also confirmed the
  eye institute entry "... (NIOH)"), plus the normalisation "traumtology → traumatology". Two shared test cases added.
  Full Dhaka run: confirmed 12 → 15 (all checked by hand), not-emergency 62 → 60.
- In that session the Geoapify MCP server was not connected, so the agent used `agent/mcp_call.py` (same MCP tools,
  called over HTTP).

## 2026-10-23: reach, coverage analysis, share, OSM links, offline app

- User request: "what else can we add? ... do all of them, one by one". Seven ideas were proposed and built in order.
- **Reach (Isoline API):** checked the docs first (ranges in seconds, up to 10 per request, `traffic`, 202 + `id` for
  long jobs, 1 credit per 5 minutes). A live call answered synchronously in ~2-3 s with two MultiPolygons. App:
  "10 / 15 min reach" button; CLI: `--reach` with `--map`. Both poll by `id` if the API answers 202.
- **Coverage analysis:** the Boundaries API `part-of` gave the Dhaka Metropolitan polygon (admin_level 6). A dry run
  listed the hospitals *before* spending isoline credits, and caught two classifier misses: the map spells
  Shaheed Suhrawardy Medical College Hospital "Sohrawardy"/"Suhrawardi" (a large government hospital shown as
  unverified private), and Dhaka Mohanagar General Hospital was missing from the government list. Fixed with shared
  test cases, then 26 isolines (~130 credits, cached in `benchmark/.cache/`). Result: 28% of the area within 15 min
  of a confirmed/government emergency department, 54% with medical college hospitals. Bangladesh Specialized Hospital
  (confirmed) is absent from the map data; the script now reports such gaps itself.
- **OpenStreetMap links** from Places' `osm_type`/`osm_id`; **Share** via the Web Share API with a WhatsApp fallback;
  **PWA**: manifest, generated icons, a network-first service worker that never caches Geoapify calls, and the last
  search kept in localStorage and shown with a "no internet" note (tested by making `fetch` fail).
- **Third hand check:** 50 fresh places, 47 right, 3 harmless "unknown"; two fixed afterwards ("nuclear medicine",
  "DigiLab"). The third ("Field office" in the second comma part) was left: catching it would let addresses such as
  "Mosque Road" mislead the classifier.
- **Emergency phone numbers:** a sub-agent read the official sites of the 7 confirmed hospitals (rules: official page
  only, copy the number exactly, "not found" rather than a guess). Only 3 publish an emergency/hotline number; I
  re-fetched those 3 pages myself before adding them to `facility_rules.json` with source and date. DMCH's own site
  was down (HTTP 500), and NIOH's only number is staffed 8:00-14:30, so none is shown for them. Fire: 102 confirmed on
  fireservice.gov.bd.
- Feedback: isolines have no reverse ("to the point") direction; Boundaries `name` stays Bangla with `lang=en`
  (English in `name_international.en`), checked with a live call before writing it down.

## Feedback ideas for Geoapify (to confirm during the benchmark)
- Mixed coordinate order across APIs (`lat,lon` vs `lon,lat`) is a frequent AI mistake. A short
  "coordinate order" note at the top of each spec would help.
- Local travel modes for South Asia (CNG / auto-rickshaw).
- Bangla-script geocoding quality.
- An MCP tool for place details or outlines (or a `geometry` option on `search_places`), so agents can
  answer "how big is it?" with `measure_geometry` alone.
