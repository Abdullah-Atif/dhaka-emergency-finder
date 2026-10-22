"""Command line entry point: python -m dhaka_emergency "Mirpur 10, Dhaka" """

import argparse
import json
import sys

from .classify import load_rules
from .finder import CATEGORIES, EMERGENCY_NUMBER, find_ranked, is_major, nearest_major
from .geoapify import GeoapifyClient, GeoapifyError
from .mapview import write_map


def _fmt_km(m):
    return "-" if m is None else f"{m / 1000:.1f} km"


def _fmt_min(s):
    return "no route" if s is None else f"{round(s / 60)} min"


def _label(list_, key):
    return next((x["en"] for x in list_ if x.get("type") == key or x.get("key") == key), key)


def _cls_line(f):
    """One line in the same words as the web app's badges."""
    return _cls_text(f) + (" · Major hospital" if is_major(f) else "")


def _cls_text(f):
    c, rules = f.cls, load_rules()
    spec = _label(rules["specialities"], c["speciality"]) if c["speciality"] else ""
    if c["ed"] == "confirmed":
        scope = " for " + spec if spec else ""
        return f"24-hour emergency department{scope} (confirmed: {c['confirmed']['source']})"
    if c["ed"] == "yes":
        return "Government hospital: 24-hour emergency department expected" + (f" · {spec}" if spec else "")
    if c["ed"] == "specialised" or (c["ed"] == "unknown" and spec):
        return "Specialised: " + spec
    if c["ed"] == "no":
        what = _label(rules["exclude"] + rules["soft_exclude"], c["type"])
        return "NOT an emergency hospital: " + what if what != c["type"] else "Map data says: no emergency department"
    if c["ed"] == "likely":
        return "Hospital: emergency department not verified" + (f" · {spec}" if spec else "")
    return "Emergency department: unknown"


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
    ap.add_argument("--major", action="store_true",
                    help="hospitals: only major ones (confirmed 24h emergency, government, medical college)")
    ap.add_argument("--map", metavar="FILE.html", help="also write an HTML map with the route to #1")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args(argv)
    if args.major and args.kind != "hospital":
        ap.error("--major works with --type hospital")

    try:
        client = GeoapifyClient()
        origin, everything = find_ranked(client, args.where, kind=args.kind, mode=args.mode)
        if origin is None:
            print(f"Could not find the location: {args.where!r}", file=sys.stderr)
            return 2
        ranked = [f for f in everything if is_major(f)] if args.major else everything
        ranked = ranked[:args.top]
        # The nearest major hospital, when it is not already #1 (see the web app's "Nearest major hospital" card).
        major = None if args.major or args.kind != "hospital" else nearest_major(everything)
        if major is not None and ranked and major is ranked[0]:
            major = None
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
            "results": [dict(vars(f), maybe_not_er=f.maybe_not_er) for f in ranked],
            "nearest_major_hospital": dict(vars(major)) if major else None,
            "classification_rules": "docs/app/facility_rules.json",
        }, ensure_ascii=False, indent=2))
    else:
        print(f"!! Emergency? Call {EMERGENCY_NUMBER} first.\n")
        print(f"From: {origin.label}")
        if origin.coarse:
            print(f"!! Could not find {args.where!r} exactly; only {origin.label!r} matched.\n"
                  "   Results are around that centre, not your location.\n"
                  '   Try a nearby landmark, a different spelling, Bangla script, or "lat,lon".')
        print(f"Nearest {args.kind} by {args.mode} travel time:\n")
        if not ranked:
            print("  No major hospital found within 10 km." if args.major else "  Nothing found within 10 km.")
        for i, f in enumerate(ranked, 1):
            print(f"{i}. {f.name}")
            print(f"   {_fmt_min(f.drive_s)} | {_fmt_km(f.drive_m)} by road | {_fmt_km(f.straight_m)} straight line")
            if f.cls:
                print(f"   {_cls_line(f)}")
            if f.opening_hours == "24/7":
                print("   Open 24/7 (map data)")
            if f.address:
                print(f"   {f.address}")
            if f.phone:
                print(f"   Phone: {f.phone}")
        if major is not None:
            extra = ""
            if ranked[0].drive_s is not None:
                extra = f" | {max(0, round((major.drive_s - ranked[0].drive_s) / 60))} min more than #1"
            print(f"\nNearest major hospital: {major.name}")
            print(f"   {_fmt_min(major.drive_s)} | {_fmt_km(major.drive_m)} by road{extra}")
            print(f"   {_cls_line(major)}")
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
