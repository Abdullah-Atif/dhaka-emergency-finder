/* Classify a health facility from its name (English / Bangla) and OpenStreetMap tags.
 * Rules live in facility_rules.json (shared with the Python CLI). Based on the research report
 * "Dhaka emergency hospital classification": OSM's hospital tag and even emergency=yes are unreliable in Dhaka,
 * so names do most of the work, in this order:
 *   1. non-hospital service words (pharmacy, homeo, dental, vet, blood bank, chamber, outpatient...) -> "no"
 *   2. a short list of hospitals with a source-confirmed 24h emergency department -> "confirmed"
 *   3. diagnostic / consultation / lab / physio words -> "no", unless the name also says "hospital"
 *   4. government general tiers (Upazila Health Complex, government medical college hospital, BIRDEM) -> "yes"
 *   5. speciality words (eye, children, trauma, burn, heart...) -> "specialised"
 *   6. any other "hospital" -> "likely" (private hospitals: not verified); clinics and the rest -> "unknown"
 *   7. OSM emergency=no -> "no"; emergency=yes only lifts "unknown" to "likely" (it is often wrong in Dhaka)
 * Result: { ed: "confirmed"|"yes"|"likely"|"specialised"|"unknown"|"no", type, speciality, confirmed, major, reasons[] }
 * major: a large general hospital (confirmed general 24h emergency, government general, or a medical college hospital).
 * The map has no bed counts, so this tier is the only size signal we can defend.
 */
(function () {
  "use strict";

  function normalize(text, rules) {
    var s = (text || "").toLowerCase().replace(/&/g, " and ").replace(/\./g, "");
    s = s.replace(/[^a-z0-9ঀ-৿/]+/g, " ").replace(/\s+/g, " ").trim();
    (rules.normalize || []).forEach(function (pair) { s = s.split(pair[0]).join(pair[1]); });
    return " " + s + " ";
  }

  // Latin words match on word boundaries ("lab" must not match "labaid"); Bangla words match as substrings.
  function has(text, word) {
    var w = word.toLowerCase().replace(/&/g, " and ").replace(/\./g, "");
    if (/[ঀ-৿]/.test(w)) return text.indexOf(w) >= 0;
    return text.indexOf(" " + w + " ") >= 0;
  }
  function any(text, words) {
    for (var i = 0; i < (words || []).length; i++) if (has(text, words[i])) return words[i];
    return null;
  }

  // Drop address tails: "Dhaka Medical College Hospital, Government hospital, Secretariat Rd, Dhaka" -> first part.
  // (keep "(...)": "LabAid Limited (Diagnostic)" says what it is)
  function firstSegment(name) { return String(name || "").split(",")[0]; }

  // Main part of a name: the first comma part, plus later parts that name a facility
  // ("National Healthcare Network, Ibrahim General Hospital, Hospital" keeps "Ibrahim General Hospital"),
  // but not Google-style category tails ("Hospital", "Government hospital") or addresses ("Secretariat Rd, Dhaka").
  function mainPart(name, rules) {
    var parts = String(name || "").split(",");
    var keep = [parts[0]];
    var generic = (rules.generic_name_parts || []).map(function (g) { return normalize(g, rules).trim(); });
    for (var i = 1; i < parts.length; i++) {
      var t = normalize(parts[i], rules);
      if (generic.indexOf(t.trim()) >= 0 || any(t, rules.address_words || [])) continue;
      if (any(t, rules.hospital_words) || any(t, rules.small_facility)) keep.push(parts[i]);
    }
    return keep.join(" , ");
  }

  function classify(rules, place) {
    var names = [place.name, place.nameEn, place.nameBn].filter(Boolean);
    var tags = place.tags || {};
    var full = normalize(names.join(" | "), rules);           // whole names, incl. address tails
    var text = normalize(names.map(function (n) { return mainPart(n, rules); }).join(" | "), rules); // main part only
    var reasons = [];
    var r = { ed: "unknown", type: "health", speciality: null, confirmed: null, major: false, reasons: reasons };

    // 1. clear non-hospitals
    for (var i = 0; i < rules.exclude.length; i++) {
      var ex = rules.exclude[i], w = any(text, ex.words);
      if (w) { r.ed = "no"; r.type = ex.type; reasons.push("name says " + ex.en + " (\"" + w + "\")"); return r; }
    }
    var hc = String(tags.healthcare || "");
    if (hc && rules.osm_not_hospital.indexOf(hc) >= 0) {
      r.ed = "no"; r.type = hc; reasons.push("map data says healthcare=" + hc); return r;
    }

    // 2. source-confirmed 24h emergency departments (exact name match on the main part of a name)
    var heads = names.map(function (n) { return normalize(firstSegment(n), rules).trim(); });
    for (var c = 0; c < rules.confirmed.length; c++) {
      var conf = rules.confirmed[c];
      var hit = conf.aliases.some(function (a) { return heads.indexOf(normalize(a, rules).trim()) >= 0; });
      if (hit) {
        r.ed = "confirmed"; r.type = "hospital"; r.confirmed = conf;
        if (conf.scope !== "general") r.speciality = conf.scope;
        r.major = conf.scope === "general";
        reasons.push("24-hour emergency confirmed by a source (" + conf.source + ")");
        return r;
      }
    }

    var hospitalWord = any(text, rules.hospital_words);
    // 3. diagnostic centres etc., unless the name also says "hospital"
    for (var j = 0; j < rules.soft_exclude.length; j++) {
      var se = rules.soft_exclude[j];
      var sw = any(text, se.words || []) ||
        ((se.prefix || []).filter(function (p) { return text.indexOf(" " + p) === 0; })[0] || null);
      if (sw && !hospitalWord) {
        r.ed = "no"; r.type = se.type; reasons.push("name says " + se.en + " (\"" + sw.trim() + "\")"); return r;
      }
    }

    // speciality from the name, else from healthcare:speciality
    var spec = null;
    for (var k = 0; k < rules.specialities.length && !spec; k++) {
      var sp = rules.specialities[k], sw2 = any(text, sp.words);
      if (sw2) { spec = sp; reasons.push("speciality word \"" + sw2 + "\""); }
    }
    if (!spec && tags["healthcare:speciality"]) {
      var vals = String(tags["healthcare:speciality"]).split(";").map(function (v) { return v.trim(); });
      var keys = vals.map(function (v) { return rules.osm_speciality[v]; }).filter(Boolean);
      if (keys.length === 1 && vals.length === 1) {
        if (keys[0] === "dental" || keys[0] === "veterinary") {
          r.ed = "no"; r.type = keys[0]; reasons.push("map data speciality: " + vals[0]); return r;
        }
        spec = rules.specialities.filter(function (s) { return s.key === keys[0]; })[0] || null;
        if (spec) reasons.push("map data speciality: " + vals[0]);
      }
    }

    var govt = any(text, rules.government_general) || any(text, rules.government_hospitals || []) ||
      (any(text, rules.medical_college_hospital) &&
        (any(full, rules.government_signal) || /^(government|public)$/.test(String(tags["operator:type"] || "")))) ||
      any(text, rules.general_tertiary);

    r.type = hospitalWord ? "hospital" : (any(text, rules.small_facility) ? "clinic" : "health");
    var general = any(text, rules.general_words || []);
    if (spec && !general) {
      r.speciality = spec.key; r.ed = spec.ed;
    } else if (spec && govt) {
      r.speciality = spec.key; r.ed = "yes"; reasons.push("government general hospital (\"" + govt + "\")");
    } else if (spec && hospitalWord) {
      r.speciality = spec.key; r.ed = "likely"; reasons.push("general hospital with a speciality (\"" + general + "\")");
    } else if (govt) {
      r.ed = "yes"; reasons.push("government / tertiary hospital (\"" + govt + "\")");
    } else if (any(text, rules.medical_college_hospital)) {
      r.ed = "likely"; reasons.push("medical college hospital (private ones usually have an emergency unit; not verified)");
    } else if (hospitalWord) {
      r.ed = "likely"; reasons.push("\"hospital\" in the name (private hospitals: emergency unit not verified)");
    } else {
      r.ed = "unknown"; reasons.push(r.type === "clinic" ? "clinic / nursing home" : "no facility word in the name");
    }
    var ew = any(text, rules.emergency_words);
    if (ew && r.ed === "unknown") { r.ed = "likely"; reasons.push("name mentions \"" + ew + "\""); }

    // 7. OSM tags: emergency=no is mostly reliable in Dhaka; emergency=yes is often wrong
    if (tags.emergency === "no") { r.ed = "no"; reasons.push("map data says emergency=no"); }
    else if (tags.emergency === "yes") {
      reasons.push("map data says emergency=yes");
      if (r.ed === "unknown") r.ed = "likely";
    }
    r.major = r.ed === "yes" || (r.ed === "likely" && !r.speciality && !!any(text, rules.medical_college_hospital));
    return r;
  }

  var api = { classify: classify, normalize: normalize };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else window.FacilityClassifier = api;
})();
