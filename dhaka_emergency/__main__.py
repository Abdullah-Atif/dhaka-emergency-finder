"""Command line entry point: python -m dhaka_emergency "Mirpur 10, Dhaka" """

import argparse
import json
import sys

from .finder import CATEGORIES, EMERGENCY_NUMBER, find
from .geoapify import GeoapifyClient, GeoapifyError
from .mapview import write_map


def _fmt_km(m):
    return "-" if m is None else f"{m / 1000:.1f} km"


def _fmt_min(s):
    return "no route" if s is None else f"{round(s / 60)} min"


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Bangla names on Windows consoles
    ap = argparse.ArgumentParser(
        prog="dhaka_emergency",
        description="Find the fastest-to-reach emergency facility in Dhaka (Geoapify).",
    )
    ap.add_argument("where", help='your location: free text ("Mirpur 10, Dhaka", "ধানমন্ডি ২৭") or "lat,lon"')
    ap.add_argument("--type", dest="kind", default="hospital", choices=sorted(CATEGORIES))
    ap.add_argument("--mode", default="drive", choices=["drive", "motorcycle", "walk"])
    ap.add_argument("--top", type=int, default=5, help="how many results to show (default 5)")
    ap.add_argument("--map", metavar="FILE.html", help="also write an HTML map with the route to #1")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args(argv)

    try:
        client = GeoapifyClient()
        origin, ranked = find(client, args.where, kind=args.kind, mode=args.mode, top=args.top)
        if origin is None:
            print(f"Could not find the location: {args.where!r}", file=sys.stderr)
            return 2
        route = None
        if args.map and ranked and ranked[0].drive_s is not None:
            best = ranked[0]
            route = client.route((origin.lon, origin.lat), (best.lon, best.lat), mode=args.mode)
    except GeoapifyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({
            "emergency_number": EMERGENCY_NUMBER,
            "origin": vars(origin),
            "results": [vars(f) for f in ranked],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"!! Emergency? Call {EMERGENCY_NUMBER} first.\n")
        print(f"From: {origin.label}")
        print(f"Nearest {args.kind} by {args.mode} travel time:\n")
        if not ranked:
            print("  Nothing found within 10 km.")
        for i, f in enumerate(ranked, 1):
            print(f"{i}. {f.name}")
            print(f"   {_fmt_min(f.drive_s)} | {_fmt_km(f.drive_m)} by road | {_fmt_km(f.straight_m)} straight line")
            if f.address:
                print(f"   {f.address}")
            if f.phone:
                print(f"   Phone: {f.phone}")
        if ranked and ranked[0].drive_s is not None:
            straight_first = min(ranked, key=lambda f: f.straight_m)
            if straight_first is not ranked[0]:
                print(f"\nNote: the closest on the map ({straight_first.name}) is NOT the fastest to reach.")

    if args.map and ranked:
        write_map(args.map, origin, ranked, route, client.api_key,
                  title=f"{args.kind.title()} near {origin.label}")
        print(f"\nMap written to {args.map}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
