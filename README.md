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

**Status:** work-in-progress prototype (v0.1.0). The CLI works and is unit-tested. The benchmark and tutorial are planned (see [Roadmap](#roadmap)).

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
benchmark/           Dhaka test locations (benchmark runner planned)
tests/               unit tests
```

## Known limitations

- The data comes from OpenStreetMap. Some hospitals are missing, have no phone number, or do not mark whether they have an emergency department.
- `traffic=approximated` is an estimate. It is not live Dhaka traffic.
- There are no CNG auto-rickshaw or rickshaw travel modes. `motorcycle` is the closest option.
- Geocoding of very informal or Bangla-script locations can fail. In that case use `lat,lon`.
- The tool does not know opening hours, bed availability or emergency capacity.
- Place-of-worship sizes are mapped areas, not capacity. A mapped outline can be a whole compound, and a containing building can be much bigger than the place itself.
- Landmark geocoding can be wrong: "BUET, Dhaka" matched a building with "BUET" in its name in Gulshan instead of the BUET campus in Palashi.

## Roadmap

- [x] CLI: geocode → places → route matrix → ranked list, HTML map, JSON, tests
- [x] Agent instructions + MCP setup (Claude Code, VS Code)
- [x] Places of worship (all religions) with size from Place Details, sorted by travel time or size
- [ ] Size check: compare mapped areas of well-known places (Baitul Mukarram, Dhakeshwari, Armenian Church, ...) with published figures
- [ ] Benchmark: about 20 Dhaka locations (English + Bangla). Compare straight-line nearest with travel-time nearest, and measure geocoding success.
- [ ] Recorded agent sessions with tool-call transcripts
- [ ] Tutorial on GitHub Pages + dev.to, with client screenshots
- [ ] Feedback report for Geoapify OpenAPI / MCP

## License

[MIT](LICENSE) © 2026 Abdullah Atif. Map data © OpenStreetMap contributors, powered by [Geoapify](https://www.geoapify.com/).
