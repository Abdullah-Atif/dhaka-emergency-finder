# Finding the *fastest* hospital in Dhaka with AI and Geoapify: MCP vs. OpenAPI

*By Abdullah Atif. Built for the [Geoapify](https://www.geoapify.com/) Open Geospatial Program, Batch #2: AI × Geospatial.*

> **Emergency in Bangladesh? Call 999 first.** This project helps you find a facility. It does not replace emergency services.

In Dhaka, the hospital that looks closest on a map is often not the one you can reach first. One-way roads,
canals, rivers and dense traffic change the answer. I wanted to see whether AI tools can answer the question
people actually have in an emergency, "where can I get to fastest?", and where they get it wrong.

I answered the same question in three ways with [Geoapify](https://www.geoapify.com/):

1. **An AI agent** that calls [Geoapify MCP](https://apidocs.geoapify.com/mcp/) tools at run time (tested in Claude Code and
   in VS Code + GitHub Copilot).
2. **A small Python CLI** that an AI coding agent wrote from the [Geoapify OpenAPI specifications](https://apidocs.geoapify.com/open-api/).
3. **A phone-friendly web app** for people who are not developers: "use my location", tap to call 999, Bangla or English.

Then I tested the pipeline on 10 real Dhaka locations, in English and in Bangla.

![Architecture: three front ends, one four-step Geoapify pipeline](images/architecture.svg)

**Try the app:** <https://abdullah-atif.github.io/dhaka-emergency-finder/app/> ·
**Code:** <https://github.com/Abdullah-Atif/dhaka-emergency-finder> (MIT)

---

## What you need

- Python 3.9 or newer (the CLI uses only the standard library)
- A free Geoapify API key from <https://myprojects.geoapify.com>
- Optional: an MCP-capable AI client (Claude Code, Claude Desktop, VS Code + GitHub Copilot, Cursor)

Put the key in an environment variable. Never commit it:

```bash
export GEOAPIFY_API_KEY=your_key            # macOS / Linux / Git Bash
$env:GEOAPIFY_API_KEY = "your_key"          # Windows PowerShell
```

---

## Part 1: The question, step by step

Whichever way you choose, the answer comes from the same four steps:

| Step | Geoapify MCP tool | Geoapify REST API |
|---|---|---|
| 1. Where am I? | `geocode_address` | Forward Geocoding |
| 2. What is nearby? | `search_places` (`healthcare.hospital`, ...) | Places |
| 3. What can I reach fastest? | `calculate_route_matrix` | Route Matrix |
| 4. How do I get there? | `calculate_route` | Routing |

Step 3 is the important one. Instead of sorting by straight-line distance, we ask for **travel times from one
source to up to 10 candidates** in a single request, and sort by time. Use `traffic=approximated`: it lowers
speeds on roads that are likely to be congested.

---

## Part 2: The AI agent (Geoapify MCP)

### Connect the client

Geoapify MCP is a remote Streamable HTTP server at `https://api.geoapify.com/v1/mcp`. It authenticates with your
key in the `x-api-key` header. In Claude Code:

```bash
claude mcp add --transport http geoapify https://api.geoapify.com/v1/mcp --header "x-api-key: YOUR_API_KEY"
```

Check that it is connected:

```text
$ claude mcp list
geoapify: https://api.geoapify.com/v1/mcp (HTTP) - ✔ Connected
```

I tested this command with Claude Code 2.1, and I also tested VS Code + GitHub Copilot (session 3 below). Setup for both
is in [agent/MCP_SETUP.md](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/agent/MCP_SETUP.md).

### Tell the agent how to behave

Tools alone are not enough. The agent needs rules, especially for an emergency use case. Mine
([agent/AGENT_INSTRUCTIONS.md](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/agent/AGENT_INSTRUCTIONS.md)) say:

- Always start with "Call 999".
- Never invent a facility, phone number or time. Every fact must come from a tool result.
- Rank by **travel time**, not by distance.
- If geocoding only matched the city, ask for a landmark instead of answering for the city centre.

### Session 1: English, every call logged

I asked: *"I am at Mirpur 10 golchottor. Where is the fastest hospital to reach by car?"* For this first session,
the agent (Claude Code) called the MCP tools through a tiny JSON-RPC helper,
[`agent/mcp_call.py`](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/agent/mcp_call.py), so that
every request and response is logged. The agent decided every call itself; the helper only sends them. It made 6 tool
calls. The [full transcript](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/agent/sessions/01-mirpur-hospital.md) is in the repository. Here is what happened:

1. `geocode_address` found the Mirpur 10 bus station with `match_type: inner_part` and confidence 1.
2. `search_places` found 10 places tagged as hospitals within 75 to 201 m.
3. `calculate_route_matrix` returned travel times of 120 to 429 seconds.
4. The first `calculate_route` call **failed**: `geometry_scope "steps" requires include_instructions to be true`.
   The error was clear, and the agent fixed it in one retry.
5. The second call worked, but returned **33 s** while the matrix said **120 s**. The agent had forgotten
   `traffic=approximated` on the route call.
6. With the same `traffic` setting the route took 121 s, which matches the matrix.

The answer it gave:

> **Emergency? Call 999.** Fastest by car: AALOK HEALTHCARE (~2 min, 254 m), FSCD Burn Unite Hospital (~2 min),
> DR. AZMAL HOSPITAL LTD. (~2 min). Note: **Medinova Hospital looks very close on the map (122 m), but by road it is
> about 1 km and 7 minutes away.**

That last line is the whole point of the project.

### Session 2: Bangla, inside Claude Code

Then I asked in Bangla, *"আমি ফার্মগেটে আছি, গাড়িতে সবচেয়ে তাড়াতাড়ি কোন হাসপাতালে যেতে পারব?"* ("I am at
Farmgate. Which hospital can I reach fastest by car?"). This time Claude Code used its **built-in MCP client**, with
only the Geoapify tools allowed. It took 4 Geoapify calls and 35 seconds
([write-up and transcript](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/agent/sessions/02-farmgate-claude-code-bangla.md)):
`geocode_address` → `search_places` (15 places) → `calculate_route_matrix` (10 targets) → `calculate_route` with
`include_instructions: true`, which was right on the first try this time.

The answer came back in Bangla. It listed Al Razi Hospital Complex first (about 1 min, 401 m, "open 24/7" from the
place's `opening_hours`). It also put Al Fateh Diagnostics, an eye institute and Brain and Mind Hospital in a separate
list as "may not be a general hospital". The instructions only ask for a general reminder; sorting the places this
way was the agent's own idea.

One gap: my instructions said "rank by travel time" but did not say to use `traffic=approximated`, so the agent used
free-flow speeds. It told the user so ("traffic not counted; real times will be longer"). The instructions now require it.

### Session 3: the same question in VS Code + GitHub Copilot

Finally I asked the session 1 question again, this time in **VS Code with GitHub Copilot in Agent mode**, which used an
OpenAI model and VS Code's own MCP client
([write-up and transcript](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/agent/sessions/03-mirpur-vscode-copilot.md)).
It made the same 4 Geoapify calls, this time with `traffic: "approximated"` on both the matrix and the route, as the
updated instructions require. It gave **the same answer as Claude Code in session 1**: AALOK HEALTHCARE, about 2 min, 254 m.

![Copilot's answer in VS Code](images/vscode-copilot-answer.png)

Two surprises worth knowing:

- **Copilot read `.vscode/mcp.json` on its own**, after a permission prompt, and so sent my Geoapify key to the model,
  because for this test I had written the key straight into that file. A key exposed like this should be replaced. Use VS Code's `inputs` prompt
  (`${input:geoapify-key}`) instead, and deny file-read requests for config files.
- Pressing **Start** on the MCP server before sending any chat message fails with *"Send a message first."* Just ask
  your question; the server starts on its own.

**What worked:** MCP tools take `{lat, lon}` objects everywhere, so the agent never mixed up coordinate order.
Error messages were precise enough to fix in one retry.

**What needed a human:** the two mistakes in session 1 (steps 4 and 5), and the missing `traffic` in session 2. Each one
became a rule in the instructions: *use `traffic: "approximated"` for driving, and the same `mode` and `traffic` for
the matrix and the route*.

---

## Part 3: The CLI, written by an AI coding agent from the OpenAPI specs

I gave Claude Code the four JSON specifications (Forward Geocoding, Places, Route Matrix, Routing) and a short
brief. The brief is in [prompts/01-prototype.md](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/prompts/01-prototype.md).
The result is a standard-library-only Python package:

```bash
python -m dhaka_emergency "Farmgate, Dhaka" --top 2
```

```text
!! Emergency? Call 999 first.

From: Farmgate, Airport Road, Tejgaon, Dhaka - 1215, Bangladesh
Nearest hospital by drive travel time:

1. Al Fateh Diagnostics
   1 min | 0.3 km by road | 0.3 km straight line
   Note: the name suggests this may not have an emergency department
   Kazi Nazrul Islam Avenue, Tejgaon, Dhaka - 1215, Bangladesh
2. Brain and Mind Hospital
   1 min | 0.5 km by road | 0.3 km straight line
   Airport Road, Tejgaon, Dhaka - 1215, Bangladesh
```

Add `--map out.html` to get a Leaflet map with Geoapify tiles and the route to the first result.

![HTML map for Farmgate: your position (blue), hospitals (markers) and the route to the fastest one (red)](images/farmgate-map.jpg)

### The core of it

The heart of the code is the ranking step: one Route Matrix request with one source and all candidates as targets
(simplified from [`geoapify.py`](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/dhaka_emergency/geoapify.py)):

```python
body = {
    "mode": mode,
    "sources": [{"location": [lon, lat]}],
    "targets": [{"location": [f.lon, f.lat]} for f in candidates],
    "traffic": "approximated",
}
data = post("https://api.geoapify.com/v1/routematrix", body)
times = data["sources_to_targets"][0]   # one row: source -> each target
```

### What the AI got right from the specs

- The right servers (`/v1` for geocoding, routing and matrix; `/v2` for places).
- Exact category keys (`healthcare.hospital`, `service.fire_station`, `emergency.ambulance_station`).
- The `x-api-key` header from the specs' `securitySchemes`, instead of putting the key in the URL.

### The trap: coordinate order

The REST APIs do not agree on coordinate order. **Routing** `waypoints` use `lat,lon`, while **Places**
`filter`/`bias` and **Route Matrix** `location` use `lon,lat`. This is the easiest bug to ship. The fix is to keep
all HTTP calls in one module, with a comment at each spot. (The MCP tools avoid the problem completely with
named `{lat, lon}` fields.)

---

## Part 4: A web app for everyone else

A CLI and an AI client are fine for developers, but in an emergency people reach for a phone. So the same pipeline
also runs as a single static page ([`docs/app/`](https://github.com/Abdullah-Atif/dhaka-emergency-finder/tree/main/docs/app),
no build step, no server), hosted free on GitHub Pages:

| Bangla, dark mode, hospitals near Mirpur 10 | English, light mode, fire service near Shahbag |
|---|---|
| ![Web app in Bangla](images/app-mobile-bangla.jpg) | ![Web app in English](images/app-mobile-english.jpg) |

What it does differently from a plain "nearest hospital" search:

- **A big "tap to call 999" button at the top**, before anything else.
- **📍 Use my location** starts the search right away, and looks up the street address in parallel.
- **Results appear in two steps.** The 10 nearest places show by distance after the Places call (1.6 s in one test on a
  good connection; it depends on the network); they are re-sorted by travel time when the Route Matrix answers, and the route to #1 is drawn on the map.
- **The same warnings as the CLI:** city-level geocoding fallback, "hospitals" whose name says diagnostic centre or eye
  hospital, and a new one for places whose name says they are something else. In the Shahbag fire-service search,
  #2 was *"Mosque of Bangladesh Fire Service & Civil Defence Headquarter"*.
- **It merges duplicates** ("radda" and "RADDA", 5 m apart, were both in the Places results).
- **Bangla and English** interface, a **Navigate** button that opens directions in Google Maps, and **tap-to-call** for
  places that have a phone number in the map data.

The browser calls Geoapify directly. Geoapify answers with `access-control-allow-origin: *`, so a static page is
enough. The pure logic (ranking, duplicate merging, the warning heuristics) has its own tests:
`node --test tests/app.test.js`.

---

## Part 5: What 10 Dhaka locations showed

`python benchmark/run.py` geocodes each location, finds up to 10 hospitals, and compares the **nearest on the map**
with the **fastest to reach**. [Full results](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/benchmark/results.md) ·
[manual review](https://github.com/Abdullah-Atif/dhaka-emergency-finder/blob/main/benchmark/NOTES.md)

| Finding | Result |
|---|---|
| The nearest hospital on the map was **not** the fastest by car | **8 of 9** locations; at least 1 minute faster in **6 of 9** (up to 6.9 min) |
| The fastest "hospital" is, by its name, a diagnostic centre or eye hospital | **3 of 9** |
| Geocoding found the right place | **8 of 10**: English 4 / 6, **Bangla 4 / 4** |

Three lessons:

**1. Bangla often geocodes better than English.** `ধানমন্ডি ২৭` found the Dhanmondi 27 junction, but
`Dhanmondi 27, Dhaka` fell back to the whole city. `বুয়েট` found the BUET campus, but `BUET, Dhaka` matched a
building with "BUET" in its name 8 km away. The full English name matched a company called "… Technology".

**2. Check `match_type`.** A city-level fallback looks like a normal answer. The only hint is
`rank.match_type = "match_by_city_or_disrict"`. My first version listed hospitals around the city centre without
any warning, and the benchmark caught it. Now the CLI warns, and the agent asks for a landmark. Some wrong
results still come back as `full_match`, though, so this check does not catch everything.

**3. "Hospital" in the map data is not always a hospital.** In Dhaka, OpenStreetMap tags many diagnostic centres,
eye hospitals and even a pharmacy as hospitals. The CLI flags names that suggest no emergency department. It is a
heuristic, so verify before relying on it.

---

## Part 6: Feedback for Geoapify

The full list, with evidence for each point, is in [feedback.md](feedback.md). The main suggestions:

- Understand Dhaka abbreviations: `R/A` → Residential Area, `Gulshan 1 Circle`.
- Penalise single-token matches for landmark queries ("BUET" → "BUET-TPHS Building").
- Wrong places (up to about 15 km away) returned as `full_match` make `match_type` less useful as a quality signal.
- Small typo in the API: `match_by_city_or_disrict`.
- MCP `geocode_address` could tell agents in its description to check `match_type` before using the result.
- An MCP tool for place details or outlines. Today `search_places` returns points only.
- A Places condition for hospitals with an emergency department (OpenStreetMap `emergency=yes`).

---

## Try it

**In your browser:** <https://abdullah-atif.github.io/dhaka-emergency-finder/app/>

**From the command line:**

```bash
git clone https://github.com/Abdullah-Atif/dhaka-emergency-finder
cd dhaka-emergency-finder
export GEOAPIFY_API_KEY=your_key
python -m dhaka_emergency "ধানমন্ডি ২৭" --type pharmacy
python -m unittest discover -s tests
```

Location data © OpenStreetMap contributors. Geocoding, places, routing and map tiles by [Geoapify](https://www.geoapify.com/).
