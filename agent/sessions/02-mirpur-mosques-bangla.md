# Session 02: "মিরপুর ১০ এর কাছে কোন কোন মসজিদ আছে, কোনটা কত বড়?"

("Which mosques are near Mirpur 10, and how big is each one?", asked in Bangla.)

- **Date:** 2026-10-19
- **Agent:** Claude Code (Claude Opus 5.5), following [AGENT_INSTRUCTIONS.md](../AGENT_INSTRUCTIONS.md)
- **Full MCP transcript:** [02-mirpur-mosques-bangla.jsonl](02-mirpur-mosques-bangla.jsonl) (2 calls)
- **CLI output for the size step:** [02-cli-sizes.txt](02-cli-sizes.txt)

## Tool calls

| # | Tool | Key arguments | Outcome |
|---|---|---|---|
| 1 | `geocode_address` | `"মিরপুর ১০ গোলচত্বর, ঢাকা"` (Bangla) | `মিরপুর-১০ গোলচক্কর` (23.80706, 90.36877), `full_match`. The Bangla input worked. |
| 2 | `search_places` | `religion.place_of_worship.islam`, 800 m, limit 6 | 6 mosques at 63 to 218 m. **Points only:** no outline or area. One result has `building: {"type": "mosque"}`, but no geometry. |

**The agent hit a limit here.** No MCP tool returns a place's outline, so `measure_geometry` has nothing to
measure. Following its instructions, the agent did not guess sizes and switched to the CLI, which uses the
Place Details REST API:

```bash
python -m dhaka_emergency "23.807057, 90.368768" --type worship --religion islam --top 6
```

## Final answer given by the agent (in Bangla, as asked)

> মিরপুর ১০ গোলচত্বরের কাছের মসজিদ (গাড়িতে সময় অনুযায়ী):
> 1. নামহীন মসজিদ: ১ মিনিট, আকার ≤ ২২১ m² (যে ভবনে আছে তার মাপ)
> 2. Shah Ali Plaza Market Masjid: ২ মিনিট, আকার ≤ ২,০৮৩ m². এটা পুরো মার্কেট ভবনের মাপ, মসজিদটা এর চেয়ে ছোট।
> 3. Baitur Mamur Jame Masjid: ২ মিনিট, **৪৪৪ m²** (মসজিদের নিজের ম্যাপ করা সীমানা)
> 4. Baitul Atik Jame Masjid: ৩ মিনিট, আকার ≤ ৩৫৭ m²
> 5. বাইতুল ফালাহ কুদ্দুস জামে মসজিদ: ৩ মিনিট, **৩৭৪ m²**
> 6. Fakir Bari Jame Masjid: ৩ মিনিট, **৫০৭ m²**, তালিকার মধ্যে নিশ্চিতভাবে সবচেয়ে বড়
>
> আকার হলো ম্যাপে আঁকা জায়গার ক্ষেত্রফল, কতজন নামাজ পড়তে পারে তা নয়। OpenStreetMap-এ ধারণক্ষমতার তথ্য নেই।

## What worked
- Bangla input in, Bangla answer out. The geocoder handled `মিরপুর ১০ গোলচত্বর` (Bangla digits) with `full_match`.

## What did not work with MCP alone
- MCP `search_places` returns points only, so the "how big?" question cannot be answered with MCP tools.
  This is the main reason the project uses **both** tracks (MCP for finding and ranking, the OpenAPI-based
  CLI for Place Details outlines).
- The largest "size" (2,083 m²) belongs to a market building, not the mosque. Without the CLI's
  "containing building" label, an agent would report it as the biggest mosque.
