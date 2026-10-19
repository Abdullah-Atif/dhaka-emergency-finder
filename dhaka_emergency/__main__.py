"""Command line entry point: python -m dhaka_emergency "Mirpur 10, Dhaka" """

import argparse
import json
import sys

from .finder import CATEGORIES, EMERGENCY_KINDS, EMERGENCY_NUMBER, RELIGIONS, SIZE_HOST, find
from .geoapify import GeoapifyClient, GeoapifyError
from .mapview import write_map


def _fmt_km(m):
    return "-" if m is None else f"{m / 1000:.1f} km"


def _fmt_min(s):
    return "no route" if s is None else f"{round(s / 60)} min"


def _fmt_size(f):
    if f.area_m2 is None:
        return "size unknown (no outline in OpenStreetMap)"
    approx = "<= " if f.area_source == SIZE_HOST else ""
    return f"{approx}{f.area_m2:,.0f} m² ({f.area_source})"


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Bangla names on Windows consoles
    ap = argparse.ArgumentParser(
        prog="dhaka_emergency",
        description="Find the fastest-to-reach emergency facility in Dhaka (Geoapify).",
    )
    ap.add_argument("where", help='your location: free text ("Mirpur 10, Dhaka", "ধানমন্ডি ২৭") or "lat,lon"')
    ap.add_argument("--type", dest="kind", default="hospital", choices=sorted(CATEGORIES))
    ap.add_argument("--religion", choices=list(RELIGIONS),
                    help="with --type worship: only mosques (islam), temples (hinduism), churches, ...")
    ap.add_argument("--sort", default="time", choices=["time", "size"],
                    help="with --type worship: fastest to reach (default) or biggest first")
    ap.add_argument("--mode", default="drive", choices=["drive", "motorcycle", "walk"])
    ap.add_argument("--top", type=int, default=5, help="how many results to show (default 5)")
    ap.add_argument("--map", metavar="FILE.html", help="also write an HTML map with the route to #1")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args(argv)
    if args.kind != "worship" and (args.religion or args.sort != "time"):
        ap.error("--religion and --sort size only work with --type worship")
    emergency = args.kind in EMERGENCY_KINDS
    label = args.kind
    if args.kind == "worship":
        label = RELIGIONS.get(args.religion, "place of worship")

    try:
        client = GeoapifyClient()
        origin, ranked = find(client, args.where, kind=args.kind, mode=args.mode, top=args.top,
                              religion=args.religion, sort=args.sort)
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
        out = {"origin": vars(origin),
               "results": [dict(vars(f), religion=f.religion, maybe_not_er=f.maybe_not_er) for f in ranked]}
        if emergency:
            out = {"emergency_number": EMERGENCY_NUMBER, **out}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if emergency:
            print(f"!! Emergency? Call {EMERGENCY_NUMBER} first.\n")
        print(f"From: {origin.label}")
        if origin.coarse:
            print(f"!! Could not find {args.where!r} exactly; only {origin.label!r} matched.\n"
                  "   Results are around that centre, not your location.\n"
                  '   Try a nearby landmark, a different spelling, Bangla script, or "lat,lon".')
        order = "biggest first" if args.sort == "size" else f"by {args.mode} travel time"
        print(f"Nearest {label} ({order}):\n")
        if not ranked:
            print("  Nothing found within 10 km.")
        for i, f in enumerate(ranked, 1):
            print(f"{i}. {f.name}" + (f" [{f.religion}]" if args.kind == "worship" and f.religion else ""))
            print(f"   {_fmt_min(f.drive_s)} | {_fmt_km(f.drive_m)} by road | {_fmt_km(f.straight_m)} straight line")
            if args.kind == "worship":
                print(f"   Size: {_fmt_size(f)}")
            if f.maybe_not_er:
                print("   Note: the name suggests this may not have an emergency department")
            if f.address:
                print(f"   {f.address}")
            if f.phone:
                print(f"   Phone: {f.phone}")
        if args.sort == "time" and ranked and ranked[0].drive_s is not None:
            straight_first = min(ranked, key=lambda f: f.straight_m)
            if straight_first is not ranked[0]:
                print(f"\nNote: the closest on the map ({straight_first.name}) is NOT the fastest to reach.")

    if args.map and ranked:
        write_map(args.map, origin, ranked, route, client.api_key,
                  title=f"{label.title()} near {origin.label}", emergency=emergency)
        print(f"\nMap written to {args.map}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
