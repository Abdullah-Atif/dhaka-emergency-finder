# Benchmark notes: manual review

[results.md](results.md) is generated automatically by `python benchmark/run.py` (10 locations, run 2026-10-21).
This file reviews every geocoding mismatch by hand and records follow-up queries that test whether a
different wording fixes the problem.

A first exploratory run used 20 locations (2026-10-19, commit `3392669`). The agreed Batch #2 scope is 10
locations, so the set was cut to 10. Pairs of the same place in English and Bangla were kept, together with
the cases that showed problems. Some follow-up queries below come from that first run.

## Manual verdict per mismatch

| # | Query | Geocoded to | Verdict |
|---|---|---|---|
| 3 | Dhanmondi 27, Dhaka | Dhaka (city only) | **Wrong.** Silent city-level fallback. The same place in Bangla (#4, `ধানমন্ডি ২৭`) worked. |
| 9 | BUET, Dhaka | "BUET-TPHS Building", Gulshan | **Wrong.** It matched a building that has "BUET" in its name about 8 km away from the campus in Palashi. |

**Corrected score: 8 / 10 correct** (English 4 / 6, Bangla 4 / 4). The automatic check agrees with the manual review.

Note on the travel-time table: #9 was ranked around the *wrong* geocoded point in Gulshan. The comparison of
"nearest on the map vs. fastest" is still valid for that point, but it is not about BUET. #3 (city-level
fallback) is excluded from the travel-time statistics.

## Follow-up: does a different wording help? (live, same day)

| Query | Geocoded to | `match_type` | Verdict |
|---|---|---|---|
| Dhanmondi Road 27, Dhaka | Road 9A, West Dhanmondi | full_match | Right area, **wrong road** |
| Dhanmondi, Dhaka | Dhanmondi (suburb) | full_match | Correct, but coarse |
| Gulshan Circle 1, Dhaka | **Gulshan 2 Circle** | full_match | **Wrong circle**, reported as a full match |
| Gulshan 1, Dhaka | a school in Gulshan 2 | full_match | Wrong |
| গুলশান ১ | গুলশান এভিনিউ | match_by_street | Close |
| Shapla Chattar, Motijheel, Dhaka | "Shapla ...", **Khilkhet** | full_match | **Wrong, about 15 km away**, reported as a full match |
| Motijheel, Dhaka | Motijheel | full_match | Correct, coarse |
| Bashundhara Residential Area, Dhaka | Bashundhara Residential Area | full_match | **Correct.** Writing "R/A" out in full fixes it. |
| Chawkbazar, Dhaka | DU Medical Center, Bokshibazar | full_match | Wrong, but nearby |
| Bangladesh University of Engineering and Technology | **"Polygon Technology Ltd."**, Banani | full_match | **Wrong.** It matched the word "Technology". |
| বুয়েট (Bangla) | BUET Central Mosque, Bokshibazar | full_match | **Correct.** |

## What this means

1. **Bangla script did better than English here.** All 4 Bangla queries were correct (4 / 4), and Bangla "বুয়েট"
   found BUET when every English form failed. English landmark names match single tokens such as "Old",
   "Technology" or "BUET" inside other place names.
2. **`match_type` catches some failures but not all.** `match_by_city_or_disrict` reliably marks the silent
   city-level fallback, and the CLI now warns when it sees it. But several clearly wrong results (Gulshan 2
   instead of 1, Khilkhet instead of Motijheel) came back as `full_match`. A client cannot detect those
   from the response alone.
3. **Common Dhaka abbreviations are not understood**: "R/A" (Residential Area), and "Circle 1" / "1 Circle".
4. **The "hospital" category needs filtering in Dhaka.** In 3 of 9 locations (6 of 16 in the first 20-location run) the fastest "hospital" is, by its
   name, a diagnostic centre, pharmacy, eye hospital or similar. The CLI now flags these.

## Feedback for Geoapify (draft)

- Treat Dhaka-style abbreviations as synonyms: `R/A` → Residential Area, `Circle 1` → `Gulshan 1`.
- Penalise single-token matches for landmark queries ("BUET" → "BUET-TPHS Building", "Technology" → a company).
- `full_match` for results that are 8 to 15 km from the intended place undermines `match_type` as a quality signal.
- Typo in the API value: `match_by_city_or_disrict` (should be "district"). Clients must match the misspelling.
- MCP `geocode_address` already returns `rank.match_type` and `confidence`, which helps. But its tool description
  could tell agents to check `match_type` before using the result, because a city-level fallback looks like a normal answer.
