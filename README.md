# Dhaka Emergency Finder

> **Emergency in Bangladesh? Call 999 first.** This project helps you find a facility. It does not replace emergency services.

Find the hospital, pharmacy, police station or fire station in Dhaka that you can **reach fastest**, ranked by real travel time instead of straight-line distance. Your location can be informal text, Bangla script or coordinates.

**Second feature: places of worship and their size.** Find nearby mosques, temples, churches, Buddhist temples and other places of worship, and see how big each one is. The size is the area of its mapped outline, from the Place Details API.

There are two ways to use it:

| | What it is | Geoapify |
|---|---|---|
| **AI agent** | Ask in plain English or Bangla in Claude Code, Claude Desktop or VS Code Copilot | [Geoapify MCP](https://apidocs.geoapify.com/mcp/) tools |
| **CLI** | `python -m dhaka_emergency "Mirpur 10"`, built with an AI coding agent from the specs | [Geoapify OpenAPI specs](https://apidocs.geoapify.com/open-api/) → REST APIs |

Built for the [Geoapify Open Geospatial Program, Batch #2: AI × Geospatial](https://www.geoapify.com/open-geospatial-program/).

**Status:** working prototype (v0.1.0). The CLI is unit-tested and has been run against the live APIs. A first
20-location benchmark and two recorded agent sessions are done. The tutorial is in progress (see [Roadmap](#roadmap)).

## First results (live Geoapify APIs, 2026-10-19)

From the [20-location Dhaka benchmark](benchmark/results.md) ([manual review](benchmark/NOTES.md)):

| Finding | Result |
|---|---|
| The nearest hospital **on the map** was **not** the fastest to reach by car | **10 of 16** locations (up to 6.9 min slower) |
| The fastest "hospital" is, by its name, a diagnostic centre, pharmacy or eye hospital | **6 of 16**, now flagged by the CLI |
| Geocoding found the right place | **14 of 20**: English 10 / 16, **Bangla 4 / 4** |
| Silent fallback to the whole city, visible only in `match_type` (e.g. "Dhanmondi 27, Dhaka") | 3 of 20, now detected and warned by the CLI |
| `"BUET, Dhaka"` / full English name | wrong place (Gulshan / a company in Banani). **`বুয়েট` in Bangla: correct.** |

Recorded AI-agent sessions with every Geoapify MCP tool call:
[hospital near Mirpur 10](agent/sessions/01-mirpur-hospital.md) ·
[mosques and their size, asked in Bangla](agent/sessions/02-mirpur-mosques-bangla.md)

### Sample output

```text
$ python -m dhaka_emergency "Farmgate, Dhaka" --top 2
!! Emergency? Call 999 first.

From: Farmgate, Airport Road, Tejgaon, Dhaka - 1215, Bangladesh
Nearest hospital (by drive travel time):

1. Al Fateh Diagnostics
   1 min | 0.3 km by road | 0.3 km straight line
   Note: the name suggests this may not have an emergency department
   Kazi Nazrul Islam Avenue, Tejgaon, Dhaka - 1215, Bangladesh
2. Brain and Mind Hospital
   1 min | 0.5 km by road | 0.3 km straight line
   Airport Road, Tejgaon, Dhaka - 1215, Bangladesh
```

```text
$ python -m dhaka_emergency "Dhanmondi 27, Dhaka"
From: Dhaka, DH, Bangladesh
!! Could not find 'Dhanmondi 27, Dhaka' exactly; only 'Dhaka, DH, Bangladesh' matched.
   Results are around that centre, not your location.
   Try a nearby landmark, a different spelling, Bangla script, or "lat,lon".
```

## Why travel time?

In Dhaka the closest facility on a map is often not the fastest to reach. Rivers, canals, one-way roads and dense traffic change the answer. The tool takes up to 10 nearby candidates and ranks them with the Route Matrix API (`traffic=approximated`). It also tells you when the closest facility on the map is *not* the fastest one.

## How it works

```
location text / "lat,lon"
   │  Forward Geocoding API      (MCP: geocode_address)       filter=countrycode:bd, bias=Dhaka
   ▼
origin (lon, lat)
   │  Places API                 (MCP: search_places)         radius 2 km → 5 km → 10 km
   ▼
up to 10 candidates
   │  Route Matrix API           (MCP: calculate_route_matrix) drive / motorcycle / walk
   ▼
ranked by travel time
   │  Routing API                (MCP: calculate_route)        route to #1 for the map
   ▼
terminal table / JSON / HTML map (Leaflet + Geoapify tiles)
```

For places of worship there is one more step:

```
each result (place_id)
   │  Place Details API          (no MCP tool yet; see below) features=details,building
   ▼
outline polygon → area in m² (MCP equivalent: measure_geometry, operation "area")
```

The size comes from the place's **own mapped outline** when OpenStreetMap has one. That outline can be a single building or a whole compound, such as the Dhakeshwari temple complex. If the place is only a point inside a bigger building (for example a mosque inside a market), the **containing building** is used and shown as an upper bound (`<=`). If neither exists, the size is reported as unknown. OpenStreetMap has almost no capacity or number-of-floors data for Dhaka, so the size is an area, not a headcount.

> **Why OpenAPI + MCP?** The MCP `search_places` tool returns points only, and there is no MCP tool for place details or building outlines. So an agent alone cannot measure a mosque. The CLI fills this gap with the Place Details REST API.

| Type (`--type`) | Geoapify category |
|---|---|
| `hospital` | `healthcare.hospital` |
| `clinic` | `healthcare.clinic_or_praxis` |
| `pharmacy` | `healthcare.pharmacy` |
| `police` | `service.police` |
| `fire` | `service.fire_station` |
| `ambulance` | `emergency.ambulance_station` |
| `worship` | `religion.place_of_worship`, or with `--religion islam` → `religion.place_of_worship.islam` (also `hinduism`, `christianity`, `buddhism`, `sikhism`, `judaism`, `multifaith`) |

## Quick start: CLI

You need Python 3.9 or newer. There are no third-party packages.

1. Get a free API key at <https://myprojects.geoapify.com>.
2. Set it as an environment variable:

   ```bash
   # macOS / Linux / Git Bash
   export GEOAPIFY_API_KEY=your_key
   # Windows PowerShell
   $env:GEOAPIFY_API_KEY = "your_key"
   ```
3. Run it:

   ```bash
   python -m dhaka_emergency "Mirpur 10, Dhaka"
   python -m dhaka_emergency "ধানমন্ডি ২৭" --type pharmacy
   python -m dhaka_emergency "23.7806, 90.4193" --type fire --mode motorcycle --map out.html
   python -m dhaka_emergency "Uttara Sector 7" --type police --json
   python -m dhaka_emergency "Mirpur 10, Dhaka" --type worship --religion islam
   python -m dhaka_emergency "Dhakeshwari Temple, Dhaka" --type worship --sort size
   ```

| Option | Meaning |
|---|---|
| `--type` | `hospital` (default), `clinic`, `pharmacy`, `police`, `fire`, `ambulance`, `worship` |
| `--religion` | with `worship`: `islam` (mosques), `hinduism` (temples), `christianity`, `buddhism`, `sikhism`, `judaism`, `multifaith` |
| `--sort` | with `worship`: `time` (default, fastest to reach) or `size` (biggest first) |
| `--mode` | `drive` (default), `motorcycle`, `walk` |
| `--top N` | number of results (default 5) |
| `--map FILE.html` | write an HTML map with all results and the route to #1 |
| `--json` | machine-readable output |

> The HTML map contains your API key (for map tiles). Do not publish generated maps.

## Quick start: AI agent (MCP)

1. Connect your AI client to Geoapify MCP: see [agent/MCP_SETUP.md](agent/MCP_SETUP.md) (Claude Code, VS Code, other clients).
2. Give it the instructions in [agent/AGENT_INSTRUCTIONS.md](agent/AGENT_INSTRUCTIONS.md).
3. Ask: *"I am at Mirpur 10 golchottor. Where is the fastest hospital to reach by car?"* or *"Which mosques are near Mirpur 10?"*

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests use a fake client, so they need no API key or network.

Manual checklist for real API runs:

- [ ] English place name → correct Dhaka location
- [ ] Bangla-script place name → correct location, or a clear "not found" message
- [ ] `lat,lon` input skips geocoding
- [ ] Each `--type` returns results in central Dhaka
- [ ] `--map` opens in a browser and shows markers and the route
- [ ] Missing key → clear error message, exit code 1
- [ ] `--type worship --religion islam` returns only mosques, each with a size or "size unknown"
- [ ] `--sort size` lists the biggest first; containing-building sizes are shown with `<=`

## Repository layout

```
dhaka_emergency/     CLI package (geoapify.py = REST client, finder.py = logic, mapview.py = HTML map)
agent/               agent instructions + MCP setup for AI clients
prompts/             prompts given to the AI coding agent, with corrections
docs/ai-log.md       what worked, what needed human guidance
benchmark/           Dhaka test locations, runner (run.py), results and manual review notes
agent/sessions/      recorded agent sessions: write-up (.md) + full MCP transcript (.jsonl)
agent/mcp_call.py    call one Geoapify MCP tool over JSON-RPC and log it (for agents without an MCP client)
tests/               unit tests
```

## Known limitations

- The data comes from OpenStreetMap. Some hospitals are missing, have no phone number, or do not mark whether they have an emergency department.
- `traffic=approximated` is an estimate. It is not live Dhaka traffic.
- There are no CNG auto-rickshaw or rickshaw travel modes. `motorcycle` is the closest option.
- Geocoding of informal English names can fail or land in the wrong place, sometimes still reported as `full_match`
  (see [benchmark/NOTES.md](benchmark/NOTES.md)). Bangla script often works better. Otherwise use `lat,lon`.
- The "not an emergency hospital" flag is a name-based heuristic, not verified data.
- The tool does not know opening hours, bed availability or emergency capacity.
- Place-of-worship sizes are mapped areas, not capacity. A mapped outline can be a whole compound, and a containing building can be much bigger than the place itself.
- Landmark geocoding can be wrong: "BUET, Dhaka" matched a building with "BUET" in its name in Gulshan instead of the BUET campus in Palashi.

## Roadmap

- [x] CLI: geocode → places → route matrix → ranked list, HTML map, JSON, tests
- [x] Agent instructions + MCP setup (Claude Code, VS Code)
- [x] Places of worship (all religions) with size from Place Details, sorted by travel time or size
- [ ] Size check: compare mapped areas of well-known places (Baitul Mukarram, Dhakeshwari, Armenian Church, ...) with published figures
- [x] Benchmark: 20 Dhaka locations (English + Bangla). Compare straight-line nearest with travel-time nearest, and measure geocoding success (`python benchmark/run.py`).
- [x] First recorded agent sessions with full MCP tool-call transcripts ([agent/sessions/](agent/sessions/))
- [ ] More sessions in Claude Desktop and VS Code Copilot, with screenshots
- [ ] Bigger benchmark (more locations, `motorcycle`, Bangla vs English for the same place)
- [ ] Tutorial on GitHub Pages + dev.to, with client screenshots
- [ ] Feedback report for Geoapify OpenAPI / MCP

## License

[MIT](LICENSE) © 2026 Abdullah Atif. Map data © OpenStreetMap contributors, powered by [Geoapify](https://www.geoapify.com/).
