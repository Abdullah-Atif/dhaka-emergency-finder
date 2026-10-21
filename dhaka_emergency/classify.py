"""Classify a health facility from its name (English / Bangla) and OpenStreetMap tags.

Python port of docs/app/classify.js; both read docs/app/facility_rules.json, and
tests/test_classify_parity.py checks that they agree on every hospital in Dhaka's map data.
See the comment at the top of classify.js for the rule order.
"""

import json
import os
import re

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "docs", "app", "facility_rules.json")
_BANGLA = re.compile(r"[ঀ-৿]")
_rules = None


def load_rules(path=RULES_PATH):
    global _rules
    if _rules is None or path != RULES_PATH:
        with open(path, encoding="utf-8") as fh:
            rules = json.load(fh)
        if path != RULES_PATH:
            return rules
        _rules = rules
    return _rules


def normalize(text, rules):
    s = (text or "").lower().replace("&", " and ").replace(".", "")
    s = re.sub(r"[^a-z0-9ঀ-৿/]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for old, new in rules.get("normalize", []):
        s = s.replace(old, new)
    return " " + s + " "


def _has(text, word):
    w = word.lower().replace("&", " and ").replace(".", "")
    if _BANGLA.search(w):
        return w in text
    return (" " + w + " ") in text


def _any(text, words):
    for w in words or []:
        if _has(text, w):
            return w
    return None


def _first_segment(name):
    return str(name or "").split(",")[0]


def _main_part(name, rules):
    """First comma part, plus later parts that name a facility; not category tails or addresses (see classify.js)."""
    parts = str(name or "").split(",")
    keep = [parts[0]]
    generic = [normalize(g, rules).strip() for g in rules.get("generic_name_parts", [])]
    for part in parts[1:]:
        t = normalize(part, rules)
        if t.strip() in generic or _any(t, rules.get("address_words", [])):
            continue
        if _any(t, rules["hospital_words"]) or _any(t, rules["small_facility"]):
            keep.append(part)
    return " , ".join(keep)


def classify(place, rules=None):
    """place: dict with name, nameEn, nameBn, tags. Returns a dict like classify.js."""
    rules = rules or load_rules()
    names = [n for n in (place.get("name"), place.get("nameEn"), place.get("nameBn")) if n]
    tags = place.get("tags") or {}
    full = normalize(" | ".join(names), rules)
    text = normalize(" | ".join(_main_part(n, rules) for n in names), rules)
    reasons = []
    r = {"ed": "unknown", "type": "health", "speciality": None, "confirmed": None, "reasons": reasons}

    for ex in rules["exclude"]:
        w = _any(text, ex["words"])
        if w:
            r.update(ed="no", type=ex["type"])
            reasons.append('name says %s ("%s")' % (ex["en"], w))
            return r
    hc = str(tags.get("healthcare") or "")
    if hc and hc in rules["osm_not_hospital"]:
        r.update(ed="no", type=hc)
        reasons.append("map data says healthcare=" + hc)
        return r

    heads = [normalize(_first_segment(n), rules).strip() for n in names]
    for conf in rules["confirmed"]:
        if any(normalize(a, rules).strip() in heads for a in conf["aliases"]):
            r.update(ed="confirmed", type="hospital", confirmed=conf)
            if conf["scope"] != "general":
                r["speciality"] = conf["scope"]
            reasons.append("24-hour emergency confirmed by a source (%s)" % conf["source"])
            return r

    hospital_word = _any(text, rules["hospital_words"])
    for se in rules["soft_exclude"]:
        sw = _any(text, se.get("words", []))
        if not sw:
            sw = next((p for p in se.get("prefix", []) if text.startswith(" " + p)), None)
        if sw and not hospital_word:
            r.update(ed="no", type=se["type"])
            reasons.append('name says %s ("%s")' % (se["en"], sw.strip()))
            return r

    spec = None
    for sp in rules["specialities"]:
        sw = _any(text, sp["words"])
        if sw:
            spec = sp
            reasons.append('speciality word "%s"' % sw)
            break
    if spec is None and tags.get("healthcare:speciality"):
        vals = [v.strip() for v in str(tags["healthcare:speciality"]).split(";")]
        keys = [rules["osm_speciality"][v] for v in vals if v in rules["osm_speciality"]]
        if len(keys) == 1 and len(vals) == 1:
            if keys[0] in ("dental", "veterinary"):
                r.update(ed="no", type=keys[0])
                reasons.append("map data speciality: " + vals[0])
                return r
            spec = next((s for s in rules["specialities"] if s["key"] == keys[0]), None)
            if spec:
                reasons.append("map data speciality: " + vals[0])

    mch = _any(text, rules["medical_college_hospital"])
    govt = (_any(text, rules["government_general"]) or _any(text, rules.get("government_hospitals", []))
            or (mch and (_any(full, rules["government_signal"])
                         or str(tags.get("operator:type") or "") in ("government", "public")))
            or _any(text, rules["general_tertiary"]))

    r["type"] = "hospital" if hospital_word else ("clinic" if _any(text, rules["small_facility"]) else "health")
    general = _any(text, rules.get("general_words", []))
    if spec and not general:
        r.update(speciality=spec["key"], ed=spec["ed"])
    elif spec and govt:
        r.update(speciality=spec["key"], ed="yes")
        reasons.append('government general hospital ("%s")' % govt)
    elif spec and hospital_word:
        r.update(speciality=spec["key"], ed="likely")
        reasons.append('general hospital with a speciality ("%s")' % general)
    elif govt:
        r["ed"] = "yes"
        reasons.append('government / tertiary hospital ("%s")' % govt)
    elif mch:
        r["ed"] = "likely"
        reasons.append("medical college hospital (private ones usually have an emergency unit; not verified)")
    elif hospital_word:
        r["ed"] = "likely"
        reasons.append('"hospital" in the name (private hospitals: emergency unit not verified)')
    else:
        reasons.append("clinic / nursing home" if r["type"] == "clinic" else "no facility word in the name")
    ew = _any(text, rules["emergency_words"])
    if ew and r["ed"] == "unknown":
        r["ed"] = "likely"
        reasons.append('name mentions "%s"' % ew)

    if tags.get("emergency") == "no":
        r["ed"] = "no"
        reasons.append("map data says emergency=no")
    elif tags.get("emergency") == "yes":
        reasons.append("map data says emergency=yes")
        if r["ed"] == "unknown":
            r["ed"] = "likely"
    return r
