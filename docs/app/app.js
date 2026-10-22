/* Dhaka Emergency Finder - web app.
 * Same pipeline as the Python CLI: geocode -> places -> route matrix -> route.
 * Pure helpers are exported for Node tests (tests/app.test.js); the UI runs only in a browser.
 */
(function () {
  "use strict";

  var DHAKA = { lat: 23.8103, lon: 90.4125 };
  var SEARCH_RADIUS = 10000;
  var RULES_VERSION = "20261022e";
  var MAX_CANDIDATES = 10;
  // Hospitals: also rank the nearest few major hospitals, found among the 200 nearest places (about 6 km in central
  // Dhaka; 100 reach only about 4 km). Cost: 11 Places credits instead of 1.
  var MAJOR_POOL = 200, MAX_MAJOR = 6;
  var CATEGORIES = {
    hospital: "healthcare.hospital",
    pharmacy: "healthcare.pharmacy",
    clinic: "healthcare.clinic_or_praxis",
    police: "service.police",
    fire: "service.fire_station",
    ambulance: "emergency.ambulance_station",
  };

  function haversineM(lat1, lon1, lat2, lon2) {
    var r = 6371000, rad = Math.PI / 180;
    var dp = (lat2 - lat1) * rad, dl = (lon2 - lon1) * rad;
    var a = Math.pow(Math.sin(dp / 2), 2) +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.pow(Math.sin(dl / 2), 2);
    return 2 * r * Math.asin(Math.sqrt(a));
  }

  // Places whose name says they are something else (seen: a mosque inside the Fire Service HQ tagged as a fire station).
  var OTHER_PLACE_HINTS = ["mosque", "masjid", "মসজিদ", "school", "canteen"];
  function maybeOtherPlace(name) {
    var n = (name || "").toLowerCase();
    return OTHER_PLACE_HINTS.some(function (h) { return n.indexOf(h) >= 0; });
  }

  // "Dhanmondi 27, Dhaka" -> only "Dhaka" matched. Note the API's spelling: "disrict".
  function isCoarse(geocodeResult) {
    var mt = ((geocodeResult && geocodeResult.rank) || {}).match_type || "";
    return mt.indexOf("match_by_city") === 0 || mt.indexOf("match_by_country") === 0;
  }

  // Rank candidates (with .time in seconds or null) fastest first; unreachable last.
  function rankByTime(items) {
    return items.slice().sort(function (a, b) {
      if (a.time == null) return b.time == null ? 0 : 1;
      if (b.time == null) return -1;
      return a.time - b.time;
    });
  }

  // OpenStreetMap often has the same place twice: "radda" and "RADDA" 5 m apart, or Dhaka Medical College Hospital as
  // a point named "Dhaka Medical College Hospital, Government hospital, Secretariat Rd, Dhaka" plus the campus outline
  // named "ঢাকা মেডিক্যাল কলেজ হাসপাতাল" (name:en "Dhaka Medical College Hospital"). Merge them; keep the nearer one,
  // the shorter (cleaner) English name and any Bangla name or phone number.
  function normName(n) { return (n || "").toLowerCase().replace(/[^a-z0-9ঀ-৿]+/g, ""); }
  function samePlace(a, b) {
    // "Shahbagh P.G. Hospital", "PG Hospital Dhaka, Bus Stop..." and "Institute of Post Graduates..." are one hospital.
    var ca = a.cls && a.cls.confirmed, cb = b.cls && b.cls.confirmed;
    if (ca && cb && ca.id === cb.id && haversineM(a.lat, a.lon, b.lat, b.lon) < 500) return true;
    var ka = [normName(a.name), normName(a.nameBn)].filter(Boolean);
    var kb = [normName(b.name), normName(b.nameBn)].filter(Boolean);
    var d = haversineM(a.lat, a.lon, b.lat, b.lon);
    return ka.some(function (x) {
      return kb.some(function (y) {
        if (x === y) return d < 30 || (x.length >= 12 && d < 300);
        var shorter = x.length < y.length ? x : y, longer = x.length < y.length ? y : x;
        return shorter.length >= 12 && longer.indexOf(shorter) === 0 && d < 300;
      });
    });
  }
  function dedupe(items) {
    var out = [];
    items.forEach(function (f) {
      var g = null;
      for (var i = 0; i < out.length && !g; i++) if (!out[i].unnamed && !f.unnamed && samePlace(out[i], f)) g = out[i];
      if (!g) { out.push(f); return; }
      if (f.name && f.name.length < g.name.length) g.name = f.name;
      g.nameBn = g.nameBn || f.nameBn;
      g.phone = g.phone || f.phone;
    });
    return out;
  }

  // Geoapify Autocomplete returns nothing for partial Bangla words ("ধানমন্ডি"), while /geocode/search finds them.
  function isBangla(text) { return /[\u0980-\u09ff]/.test(text || ""); }
  function isLatLon(text) { return /^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$/.test(text || ""); }

  // Keep the travel-time order, but move places classified as "not an emergency facility" to the end.
  function demoteNonEmergency(items) {
    var ok = [], no = [];
    items.forEach(function (f) { (f.cls && f.cls.ed === "no" ? no : ok).push(f); });
    return ok.concat(no);
  }

  // "Major" = a large general hospital (classify.js: confirmed general 24h emergency, government, medical college).
  // The map has no bed counts, so this tier is the only size signal we can defend.
  function isMajor(f) { return !!(f.cls && f.cls.major); }
  function nearestMajor(ranked) {
    return ranked.filter(function (f) { return isMajor(f) && f.time != null; })[0] || null;
  }
  // Spelling-proof key: consonants of the first real word ("Shahid Sohrawardy" and "Shaheed Suhrawardi" -> "shrwrd").
  function nameKey(name) {
    var w = String(name || "").toLowerCase().split(/[^a-z]+/).filter(function (x) {
      return x && !/^(shaheed|shahid|the|dr)$/.test(x);
    })[0] || "";
    return w.replace(/[aeiouy]/g, "");
  }
  // Two entries of one campus. Distance alone is not enough: BIRDEM is 80 m from PG Hospital.
  function sameHospital(a, b) {
    var k = nameKey(a.name);
    return !!k && k === nameKey(b.name) && haversineM(a.lat, a.lon, b.lat, b.lon) < 300;
  }
  // The nearest places, plus major hospitals from further away that are not among them (one entry per hospital).
  function withMajor(items) {
    var out = items.slice(0, MAX_CANDIDATES), added = 0;
    items.slice(MAX_CANDIDATES).forEach(function (f) {
      if (added >= MAX_MAJOR || !isMajor(f)) return;
      if (out.some(function (g) { return isMajor(g) && sameHospital(g, f); })) return;
      out.push(f);
      added++;
    });
    return out;
  }

  var helpers = { isMajor: isMajor, nearestMajor: nearestMajor, withMajor: withMajor,
                  demoteNonEmergency: demoteNonEmergency, isBangla: isBangla, isLatLon: isLatLon, haversineM: haversineM, isCoarse: isCoarse,
                  rankByTime: rankByTime, dedupe: dedupe, maybeOtherPlace: maybeOtherPlace, CATEGORIES: CATEGORIES };
  if (typeof module !== "undefined" && module.exports) { module.exports = helpers; return; }

  // ---------------------------------------------------------------- browser UI

  var T = {
    en: {
      call: "Emergency? Tap to call 999", where: "Where are you?", placeholder: "e.g. Mirpur 10, ধানমন্ডি ২৭, or lat,lon",
      myloc: "Use my location", find: "Find fastest", what: "What do you need?", how: "How are you travelling?",
      hospital: "Hospital", pharmacy: "Pharmacy", clinic: "Clinic", police: "Police", fire: "Fire service", ambulance: "Ambulance",
      drive: "Car", motorcycle: "Motorcycle", walk: "Walk",
      searching: "Searching…", ranking: "Nearest by distance. Checking travel times…", locating: "Getting your location…", nothing: "Nothing found within 10 km.",
      notfound: "Could not find that place. Try a nearby landmark, Bangla script, or lat,lon.",
      coarse: "Could not find that exact place; only “{x}” matched. Results are around its centre, not your location. Try a nearby landmark or Bangla script.",
      from: "From", min: "min", byroad: "by road", straight: "straight line", noroute: "no route",
      other: "Name suggests this may be a different place (e.g. a mosque inside the compound), not the service itself",
      unnamedwarn: "No name in the map data: it may be a small clinic or office. Check before going.",
      showall: "Show all {n} places", showless: "Show top 5",
      cls_confirmed: "24-hour emergency department (confirmed by a source)",
      cls_confirmed_spec: "24-hour emergency for {x} (confirmed by a source)",
      cls_yes: "Government hospital: 24-hour emergency department expected",
      cls_likely: "Hospital: emergency department not verified",
      cls_spec: "Specialised: {x}",
      cls_unknown: "Emergency department: unknown",
      cls_no: "Not an emergency hospital: {x}",
      cls_no_map: "Map data says: no emergency department",
      open247: "Open 24/7 (map data)", source: "source",
      notfastest: "The closest on the map ({x}) is not the fastest to reach.",
      callbtn: "Call", navigate: "Navigate", route: "Show route",
      majoronly: "Major hospitals only",
      majorhint: "Large general hospitals: a confirmed 24-hour emergency department, government hospitals and medical college hospitals. The map has no bed counts.",
      majorcard: "Nearest major hospital", majorslower: "{x} min more than #1", majorbadge: "Major hospital",
      nomajor: "No major hospital found within 10 km. Turn off “Major hospitals only” to see all places.",
      keytitle: "Geoapify API key needed", keyhelp: "This demo needs a free Geoapify API key. It is stored only in this browser.",
      keysave: "Save key", geoerr: "Could not get your location. Type it instead.",
      disclaimer: "Map data may be incomplete. A place may be closed or have no emergency department. Times are estimates with approximate traffic.",
      lang: "বাংলা",
    },
    bn: {
      call: "জরুরি অবস্থা? ৯৯৯-এ কল করতে চাপুন", where: "আপনি কোথায় আছেন?", placeholder: "যেমন: মিরপুর ১০, ধানমন্ডি ২৭, বা lat,lon",
      myloc: "আমার অবস্থান", find: "দ্রুততম খুঁজুন", what: "কী দরকার?", how: "কীভাবে যাবেন?",
      hospital: "হাসপাতাল", pharmacy: "ফার্মেসি", clinic: "ক্লিনিক", police: "পুলিশ", fire: "ফায়ার সার্ভিস", ambulance: "অ্যাম্বুলেন্স",
      drive: "গাড়ি", motorcycle: "মোটরসাইকেল", walk: "হেঁটে",
      searching: "খোঁজা হচ্ছে…", ranking: "দূরত্ব অনুযায়ী কাছেরগুলো। যাতায়াতের সময় হিসাব করা হচ্ছে…", locating: "আপনার অবস্থান নেওয়া হচ্ছে…", nothing: "১০ কিমির মধ্যে কিছু পাওয়া যায়নি।",
      notfound: "জায়গাটা পাওয়া যায়নি। কাছের কোনো পরিচিত জায়গা, বাংলায়, বা lat,lon লিখে চেষ্টা করুন।",
      coarse: "ঠিক জায়গাটা পাওয়া যায়নি, শুধু “{x}” মিলেছে। ফলাফল সেটার কেন্দ্রের আশেপাশের, আপনার অবস্থানের নয়। কাছের পরিচিত জায়গা বা বাংলায় লিখে চেষ্টা করুন।",
      from: "যেখান থেকে", min: "মিনিট", byroad: "রাস্তায়", straight: "সোজাসুজি", noroute: "রাস্তা নেই",
      other: "নাম দেখে মনে হচ্ছে এটা অন্য কোনো জায়গা (যেমন প্রাঙ্গণের ভেতরের মসজিদ), সেবাকেন্দ্রটি নিজে নয়",
      unnamedwarn: "ম্যাপে এর কোনো নাম নেই: এটা ছোট ক্লিনিক বা অফিস হতে পারে। যাওয়ার আগে নিশ্চিত হয়ে নিন।",
      showall: "সব {n}টি জায়গা দেখুন", showless: "শুধু প্রথম ৫টি দেখুন",
      cls_confirmed: "২৪ ঘণ্টা জরুরি বিভাগ (সূত্রে নিশ্চিত)",
      cls_confirmed_spec: "২৪ ঘণ্টা জরুরি বিভাগ: {x} (সূত্রে নিশ্চিত)",
      cls_yes: "সরকারি হাসপাতাল: ২৪ ঘণ্টা জরুরি বিভাগ থাকার কথা",
      cls_likely: "হাসপাতাল: জরুরি বিভাগ যাচাই করা হয়নি",
      cls_spec: "বিশেষায়িত: {x}",
      cls_unknown: "জরুরি বিভাগ: অজানা",
      cls_no: "জরুরি হাসপাতাল নয়: {x}",
      cls_no_map: "ম্যাপের তথ্য অনুযায়ী জরুরি বিভাগ নেই",
      open247: "২৪/৭ খোলা (ম্যাপের তথ্য)", source: "সূত্র",
      notfastest: "ম্যাপে সবচেয়ে কাছেরটি ({x}) সবচেয়ে তাড়াতাড়ি পৌঁছানোর নয়।",
      callbtn: "কল", navigate: "নেভিগেট", route: "রাস্তা দেখুন",
      majoronly: "শুধু বড় হাসপাতাল",
      majorhint: "বড় সাধারণ হাসপাতাল: সূত্রে নিশ্চিত ২৪ ঘণ্টা জরুরি বিভাগ, সরকারি হাসপাতাল ও মেডিকেল কলেজ হাসপাতাল। ম্যাপে শয্যা সংখ্যা নেই।",
      majorcard: "কাছের বড় হাসপাতাল", majorslower: "১ নম্বরের চেয়ে {x} মিনিট বেশি", majorbadge: "বড় হাসপাতাল",
      nomajor: "১০ কিমির মধ্যে কোনো বড় হাসপাতাল পাওয়া যায়নি। সব জায়গা দেখতে “শুধু বড় হাসপাতাল” বন্ধ করুন।",
      keytitle: "Geoapify API key দরকার", keyhelp: "এই ডেমো চালাতে একটা ফ্রি Geoapify API key লাগবে। এটা শুধু এই ব্রাউজারেই থাকবে।",
      keysave: "Key সেভ করুন", geoerr: "অবস্থান পাওয়া যায়নি। হাতে লিখে দিন।",
      disclaimer: "ম্যাপের তথ্য অসম্পূর্ণ হতে পারে। কোনো জায়গা বন্ধ থাকতে পারে বা সেখানে জরুরি বিভাগ না-ও থাকতে পারে। সময় আনুমানিক, যানজট ধরে।",
      lang: "English",
    },
  };

  var state = { lang: "en", kind: "hospital", mode: "drive", origin: null, results: [], routeLayer: null, pending: false, showAll: false, rules: null,
                majorOnly: false, resultsKind: null };
  var map, markerLayer;
  var $ = function (id) { return document.getElementById(id); };
  function t(k) { return T[state.lang][k]; }

  function apiKey() {
    var cfg = (window.DEF_CONFIG || {}).apiKey;
    if (cfg) return cfg;
    try { return localStorage.getItem("geoapifyKey") || ""; } catch (e) { return ""; }
  }

  function getJSON(url, body) {
    var sep = url.indexOf("?") >= 0 ? "&" : "?";
    var opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    return fetch(url + sep + "apiKey=" + encodeURIComponent(apiKey()), opts).then(function (r) {
      if (!r.ok) throw new Error("Geoapify HTTP " + r.status);
      return r.json();
    });
  }

  function geocode(text) {
    var m = text.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
    if (m) return Promise.resolve({ lat: +m[1], lon: +m[2], label: m[1] + ", " + m[2], coarse: false });
    var q = "https://api.geoapify.com/v1/geocode/search?format=json&limit=1&lang=en&filter=countrycode:bd" +
      "&bias=proximity:" + DHAKA.lon + "," + DHAKA.lat + "&text=" + encodeURIComponent(text);
    return getJSON(q).then(function (d) {
      var h = (d.results || [])[0];
      return h ? { lat: h.lat, lon: h.lon, label: h.formatted, coarse: isCoarse(h) } : null;
    });
  }

  function suggest(text) {
    var common = "&format=json&limit=5&lang=en&filter=countrycode:bd&bias=proximity:" + DHAKA.lon + "," + DHAKA.lat +
      "&text=" + encodeURIComponent(text);
    function toItems(d) {
      return (d.results || []).map(function (h) {
        return { main: h.address_line1 || h.formatted, sub: h.address_line2 || "", lat: h.lat, lon: h.lon,
                 label: h.formatted, coarse: isCoarse(h) };
      });
    }
    return getJSON("https://api.geoapify.com/v1/geocode/autocomplete?" + common.slice(1)).then(toItems).then(function (items) {
      if (items.length || !isBangla(text)) return items;
      return getJSON("https://api.geoapify.com/v1/geocode/search?" + common.slice(1)).then(toItems);
    });
  }

  function reverse(lat, lon) {
    return getJSON("https://api.geoapify.com/v1/geocode/reverse?format=json&lang=en&lat=" + lat + "&lon=" + lon)
      .then(function (d) { var h = (d.results || [])[0]; return h ? h.formatted : lat.toFixed(5) + ", " + lon.toFixed(5); })
      .catch(function () { return lat.toFixed(5) + ", " + lon.toFixed(5); });
  }

  function findCandidates(origin, kind) {
    // One request: the 10 nearest places within 10 km (bias=proximity sorts nearest first). For hospitals, ask for
    // the 200 nearest and keep the 10 nearest plus the nearest major hospitals among the rest.
    var limit = kind === "hospital" ? MAJOR_POOL : MAX_CANDIDATES;
    var q = "https://api.geoapify.com/v2/places?lang=en&limit=" + limit + "&categories=" + CATEGORIES[kind] +
      "&filter=circle:" + origin.lon + "," + origin.lat + "," + SEARCH_RADIUS + "&bias=proximity:" + origin.lon + "," + origin.lat;
    return getJSON(q).then(function (d) { return d.features || []; }).then(function (features) {
      return dedupe(features.map(function (ft) {
        var p = ft.properties || {};
        var raw = (p.datasource || {}).raw || {};
        return {
          // Prefer the English name; keep the Bangla one for the Bangla interface. Unnamed: show the building/street.
          name: raw["name:en"] || p.name || ("(unnamed) · " + (p.address_line1 || "")).replace(/ · $/, ""),
          nameBn: raw["name:bn"] || (isBangla(p.name) ? p.name : ""),
          unnamed: !p.name && !raw["name:en"],
          address: p.address_line2 || p.formatted || "",
          lat: p.lat, lon: p.lon, categories: p.categories || [],
          phone: (p.contact || {}).phone || raw.phone || raw["contact:phone"] || "",
          straight: haversineM(origin.lat, origin.lon, p.lat, p.lon), time: null, dist: null,
          tags: { opening_hours: raw.opening_hours },
          cls: (state.rules && window.FacilityClassifier && (kind === "hospital" || kind === "clinic"))
            ? window.FacilityClassifier.classify(state.rules, { name: p.name, nameEn: raw["name:en"], nameBn: raw["name:bn"],
                tags: { emergency: raw.emergency, healthcare: raw.healthcare, "healthcare:speciality": raw["healthcare:speciality"],
                        "operator:type": raw["operator:type"] } })
            : null,
        };
      }));
    }).then(withMajor);
  }

  function rank(origin, items, mode) {
    if (!items.length) return Promise.resolve([]);
    var body = {
      mode: mode, sources: [{ location: [origin.lon, origin.lat] }],
      targets: items.map(function (f) { return { location: [f.lon, f.lat] }; }),
    };
    if (mode !== "walk") body.traffic = "approximated";
    return getJSON("https://api.geoapify.com/v1/routematrix", body).then(function (d) {
      (d.sources_to_targets[0] || []).forEach(function (c) {
        if (c.time != null) { items[c.target_index].time = c.time; items[c.target_index].dist = c.distance; }
      });
      return demoteNonEmergency(rankByTime(items));
    });
  }

  function route(origin, dest, mode) {
    // Routing waypoints are lat,lon (unlike Places and Route Matrix, which use lon,lat).
    var q = "https://api.geoapify.com/v1/routing?format=geojson&mode=" + mode +
      (mode !== "walk" ? "&traffic=approximated" : "") +
      "&waypoints=" + origin.lat + "," + origin.lon + "|" + dest.lat + "," + dest.lon;
    return getJSON(q).then(function (d) { return (d.features || [])[0] || null; });
  }

  // ---------------------------------------------------------------- rendering

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtMin(s) {
    if (s == null) return state.pending ? "…" : t("noroute");
    return Math.max(1, Math.round(s / 60)) + " " + t("min");
  }
  function ruleLabel(list, key) {
    var hit = (list || []).filter(function (x) { return x.type === key || x.key === key; })[0];
    return hit ? hit[state.lang === "bn" ? "bn" : "en"] : key;
  }
  function clsBadge(f) {
    var c = f.cls, R = state.rules;
    if (!c || !R) return "";
    var spec = c.speciality ? ruleLabel(R.specialities, c.speciality) : "";
    var html;
    if (c.ed === "confirmed") {
      html = '<p class="badge ok">🚑 ' + esc(t(c.speciality ? "cls_confirmed_spec" : "cls_confirmed").replace("{x}", spec)) +
        ' <a href="' + esc(c.confirmed.source) + '" target="_blank" rel="noopener">' + esc(t("source")) + "</a></p>";
    } else if (c.ed === "yes") {
      html = '<p class="badge ok">🚑 ' + esc(t("cls_yes")) + (spec ? " · " + esc(spec) : "") + "</p>";
    } else if (c.ed === "specialised" || (c.ed === "unknown" && spec)) {
      html = '<p class="badge spec">' + esc(t("cls_spec").replace("{x}", spec)) + "</p>";
    } else if (c.ed === "no") {
      var what = ruleLabel((R.exclude || []).concat(R.soft_exclude || []), c.type);
      html = '<p class="badge bad">⛔ ' + esc(what === c.type ? t("cls_no_map") : t("cls_no").replace("{x}", what)) + "</p>";
    } else if (c.ed === "likely") {
      html = '<p class="badge info">' + esc(t("cls_likely")) + (spec ? " · " + esc(spec) : "") + "</p>";
    } else {
      html = '<p class="badge info">' + esc(t("cls_unknown")) + "</p>";
    }
    if (c.major) html += '<p class="badge major">🏥 ' + esc(t("majorbadge")) + "</p>";
    if (f.tags && f.tags.opening_hours === "24/7") html += '<p class="badge info">🕐 ' + esc(t("open247")) + "</p>";
    return html;
  }

  // key: index into shown(), or "major" for the nearest-major-hospital card
  function actions(f, key) {
    var phone = f.phone ? '<a class="btn small" href="tel:' + esc(f.phone.replace(/[^+\d]/g, "")) + '">📞 ' + esc(t("callbtn")) + "</a>" : "";
    var nav = '<a class="btn small" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=' +
      f.lat + "," + f.lon + '">🧭 ' + esc(t("navigate")) + "</a>";
    return '<div class="actions"><button class="btn small" data-route="' + key + '">🗺 ' + esc(t("route")) + "</button>" + phone + nav + "</div>";
  }

  function displayName(f) { return state.lang === "bn" && f.nameBn ? f.nameBn : f.name; }
  function fmtKm(m) { return m == null ? "–" : (m / 1000).toFixed(1) + " km"; }

  function setStatus(html, kind) {
    var el = $("status");
    el.className = "status" + (kind ? " " + kind : "");
    el.innerHTML = html || "";
    el.hidden = !html;
  }

  function renderText() {
    document.documentElement.lang = state.lang === "bn" ? "bn" : "en";
    document.querySelectorAll("[data-t]").forEach(function (el) { el.textContent = t(el.getAttribute("data-t")); });
    $("where-input").placeholder = t("placeholder");
    if (state.results.length) renderResults();
  }

  function renderResults() {
    var o = state.origin, list = $("results");
    var html = '<p class="from">' + esc(t("from")) + ": " + esc(o.label) + "</p>";
    if (state.pending) html += '<p class="note">⏳ ' + esc(t("ranking")) + "</p>";
    if (!state.results.length) html += '<p class="muted">' + esc(t("nothing")) + "</p>";
    else if (!visible().length) html += '<p class="muted">' + esc(t("nomajor")) + "</p>";
    var mj = majorCard();
    if (mj) {
      var first = shown()[0];
      var extra = first && first.time != null ? Math.round((mj.time - first.time) / 60) : 0;
      html += '<article class="card major"><p class="major-title">🏥 ' + esc(t("majorcard")) + "</p>" +
        '<div class="row"><h3>' + esc(displayName(mj)) + '</h3><span class="time">' + esc(fmtMin(mj.time)) + "</span></div>" +
        '<p class="meta">' + esc(fmtKm(mj.dist)) + " " + esc(t("byroad")) +
        (extra > 0 ? " · " + esc(t("majorslower").replace("{x}", extra)) : "") + "</p>" +
        (mj.address ? '<p class="addr">' + esc(mj.address) + "</p>" : "") + clsBadge(mj) + actions(mj, "major") + "</article>";
    }
    shown().forEach(function (f, i) {
      html += '<article class="card' + (i === 0 ? " best" : "") + '">' +
        '<div class="row"><span class="rank">' + (i + 1) + '</span><h3>' + esc(displayName(f)) + "</h3>" +
        '<span class="time">' + esc(fmtMin(f.time)) + "</span></div>" +
        '<p class="meta">' + esc(fmtKm(f.dist)) + " " + esc(t("byroad")) + " · " + esc(fmtKm(f.straight)) + " " + esc(t("straight")) + "</p>" +
        (f.address ? '<p class="addr">' + esc(f.address) + "</p>" : "") +
        (f.cls ? clsBadge(f) : (maybeOtherPlace(f.name) ? '<p class="warn">⚠ ' + esc(t("other")) + "</p>" : "")) +
        (f.unnamed ? '<p class="warn">⚠ ' + esc(t("unnamedwarn")) + "</p>" : "") +
        (f.phone ? '<p class="addr">' + esc(f.phone) + "</p>" : "") +
        actions(f, i) + "</article>";
    });
    if (!state.pending && visible().length > 5) {
      html += '<button class="btn small more" id="more">' +
        esc(state.showAll ? t("showless") : t("showall").replace("{n}", visible().length)) + "</button>";
    }
    var reach = visible().filter(function (f) { return f.time != null; });
    if (!state.pending && reach.length > 1) {
      var nearest = reach.reduce(function (a, b) { return a.straight <= b.straight ? a : b; });
      if (nearest !== reach[0]) html += '<p class="note">ℹ ' + esc(t("notfastest").replace("{x}", displayName(nearest))) + "</p>";
    }
    html += '<p class="muted small">' + esc(t("disclaimer")) + "</p>";
    list.innerHTML = html;
    var more = $("more");
    if (more) more.addEventListener("click", function () { state.showAll = !state.showAll; renderResults(); drawMap(); });
    list.querySelectorAll("[data-route]").forEach(function (b) {
      b.addEventListener("click", function () {
        var k = b.getAttribute("data-route");
        showRoute(k === "major" ? majorCard() : shown()[+k]);
      });
    });
  }

  function majorFilter() { return state.majorOnly && state.resultsKind === "hospital"; }
  function visible() { return majorFilter() ? state.results.filter(isMajor) : state.results; }
  function shown() { var v = visible(); return state.showAll ? v : v.slice(0, 5); }
  // The nearest major hospital, when it is not already the first result (and the list is not major-only already).
  function majorCard() {
    if (state.pending || state.resultsKind !== "hospital" || majorFilter()) return null;
    var mj = nearestMajor(state.results);
    return mj && mj !== shown()[0] ? mj : null;
  }

  function drawMap() {
    var o = state.origin;
    markerLayer.clearLayers();
    var bounds = [[o.lat, o.lon]];
    L.circleMarker([o.lat, o.lon], { radius: 9, color: "#1565c0", fillOpacity: 0.9 }).addTo(markerLayer);
    shown().forEach(function (f, i) {
      bounds.push([f.lat, f.lon]);
      L.marker([f.lat, f.lon], {
        icon: L.divIcon({ className: "pin" + (i === 0 ? " best" : ""), html: String(i + 1), iconSize: [26, 26] }),
      }).addTo(markerLayer).bindPopup("<b>" + esc(displayName(f)) + "</b><br>" + esc(fmtMin(f.time)));
    });
    var mj = majorCard();
    if (mj && shown().indexOf(mj) < 0) {
      bounds.push([mj.lat, mj.lon]);
      L.marker([mj.lat, mj.lon], { icon: L.divIcon({ className: "pin major", html: "H", iconSize: [26, 26] }) })
        .addTo(markerLayer).bindPopup("<b>" + esc(displayName(mj)) + "</b><br>" + esc(fmtMin(mj.time)));
    }
    map.invalidateSize();
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 17, animate: false });
  }

  function showRoute(f) {
    if (!f || f.time == null) return;
    route(state.origin, f, state.mode).then(function (feat) {
      if (state.routeLayer) map.removeLayer(state.routeLayer);
      if (!feat) return;
      state.routeLayer = L.geoJSON(feat, { style: { color: "#b00020", weight: 5 } }).addTo(map);
      var b = state.routeLayer.getBounds().extend([state.origin.lat, state.origin.lon]);
      shown().forEach(function (r) { b.extend([r.lat, r.lon]); });
      map.fitBounds(b, { padding: [30, 30], maxZoom: 17, animate: false });
      $("map").scrollIntoView({ behavior: "smooth", block: "nearest" });
    }).catch(function () {});
  }

  function run(originPromise) {
    if (!apiKey()) { $("keybox").hidden = false; return; }
    setStatus(esc(t("searching")));
    $("results").innerHTML = "";
    state.showAll = false;
    var mode = state.mode, kind = state.kind;
    originPromise.then(function (origin) {
      if (!origin) { setStatus(esc(t("notfound")), "error"); return null; }
      state.origin = origin;
      if (origin.coarse) setStatus("⚠ " + esc(t("coarse").replace("{x}", origin.label)), "error");
      else setStatus("");
      return findCandidates(origin, kind).then(function (items) {
        // Show the nearest places at once; re-sort when travel times arrive.
        state.results = items.slice().sort(function (a, b) { return a.straight - b.straight; });
        state.resultsKind = kind;
        state.pending = true;
        if (state.routeLayer) { map.removeLayer(state.routeLayer); state.routeLayer = null; }
        $("map").hidden = false;
        renderResults();
        drawMap();
        return rank(origin, items, mode);
      });
    }).then(function (ranked) {
      state.pending = false;
      if (!ranked) return;
      state.results = ranked;
      if (state.routeLayer) { map.removeLayer(state.routeLayer); state.routeLayer = null; }
      $("map").hidden = false;
      renderResults();
      drawMap();
      showRoute(shown()[0]);
    }).catch(function (e) {
      state.pending = false;
      setStatus(esc(String(e.message || e)), "error");
    });
  }

  function loadRules() {
    fetch("facility_rules.json?v=" + RULES_VERSION).then(function (r) { return r.json(); })
      .then(function (j) { state.rules = j; }).catch(function () { state.rules = null; });
  }

  function init() {
    loadRules();
    try { if ((localStorage.getItem("lang") || "") === "bn") state.lang = "bn"; } catch (e) {}
    map = L.map("map", { zoomControl: true });
    L.tileLayer("https://maps.geoapify.com/v1/tile/osm-bright/{z}/{x}/{y}.png?apiKey=" + encodeURIComponent(apiKey()), {
      maxZoom: 20,
      attribution: 'Powered by <a href="https://www.geoapify.com/">Geoapify</a> | &copy; OpenStreetMap contributors',
    }).addTo(map);
    map.setView([DHAKA.lat, DHAKA.lon], 12);
    markerLayer = L.layerGroup().addTo(map);

    document.querySelectorAll("[data-kind]").forEach(function (b) {
      b.addEventListener("click", function () {
        state.kind = b.getAttribute("data-kind");
        document.querySelectorAll("[data-kind]").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
        $("majorwrap").hidden = state.kind !== "hospital";
      });
    });
    try { state.majorOnly = localStorage.getItem("majorOnly") === "1"; } catch (e) {}
    var majorBox = $("majoronly");
    majorBox.checked = state.majorOnly;
    majorBox.addEventListener("change", function () {
      state.majorOnly = majorBox.checked;
      try { localStorage.setItem("majorOnly", state.majorOnly ? "1" : ""); } catch (e) {}
      if (!state.results.length || state.pending) return;
      if (state.routeLayer) { map.removeLayer(state.routeLayer); state.routeLayer = null; }
      renderResults();
      drawMap();
      showRoute(shown()[0]);
    });
    document.querySelectorAll("[data-mode]").forEach(function (b) {
      b.addEventListener("click", function () {
        state.mode = b.getAttribute("data-mode");
        document.querySelectorAll("[data-mode]").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
      });
    });
    var sug = { items: [], active: -1, seq: 0, timer: null };
    var input = $("where-input"), list = $("suggest");
    function closeSuggest() { list.hidden = true; list.innerHTML = ""; sug.items = []; sug.active = -1; input.setAttribute("aria-expanded", "false"); }
    function pick(i) {
      var it = sug.items[i];
      if (!it) return;
      input.value = it.label;
      closeSuggest();
      run(Promise.resolve({ lat: it.lat, lon: it.lon, label: it.label, coarse: it.coarse }));
    }
    function renderSuggest() {
      list.innerHTML = sug.items.map(function (it, i) {
        return '<li role="option" id="sug-' + i + '" data-i="' + i + '"' + (i === sug.active ? ' aria-selected="true"' : "") + ">" +
          '<span class="s-main">' + esc(it.main) + '</span><span class="s-sub">' + esc(it.sub) + "</span></li>";
      }).join("");
      list.hidden = !sug.items.length;
      input.setAttribute("aria-expanded", String(!!sug.items.length));
      if (sug.active >= 0) input.setAttribute("aria-activedescendant", "sug-" + sug.active);
      else input.removeAttribute("aria-activedescendant");
    }
    input.addEventListener("input", function () {
      clearTimeout(sug.timer);
      var text = input.value.trim();
      if (text.length < 3 || isLatLon(text) || !apiKey()) { closeSuggest(); return; }
      var mySeq = ++sug.seq;
      sug.timer = setTimeout(function () {
        suggest(text).then(function (items) {
          if (mySeq !== sug.seq) return; // a newer keystroke won
          sug.items = items; sug.active = -1; renderSuggest();
        }).catch(function () {});
      }, 300);
    });
    input.addEventListener("keydown", function (e) {
      if (list.hidden) return;
      if (e.key === "ArrowDown") { e.preventDefault(); sug.active = Math.min(sug.active + 1, sug.items.length - 1); renderSuggest(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sug.active = Math.max(sug.active - 1, -1); renderSuggest(); }
      else if (e.key === "Enter" && sug.active >= 0) { e.preventDefault(); pick(sug.active); }
      else if (e.key === "Escape") { closeSuggest(); }
    });
    // mousedown fires before the input loses focus, so the click is not lost
    list.addEventListener("mousedown", function (e) {
      var li = e.target.closest("li[data-i]");
      if (li) { e.preventDefault(); pick(+li.getAttribute("data-i")); }
    });
    input.addEventListener("blur", function () { setTimeout(closeSuggest, 150); });

    $("search").addEventListener("submit", function (e) {
      e.preventDefault();
      sug.seq++; clearTimeout(sug.timer); closeSuggest();
      var text = input.value.trim();
      if (text) run(geocode(text));
    });
    $("myloc").addEventListener("click", function () {
      if (!navigator.geolocation) { setStatus(esc(t("geoerr")), "error"); return; }
      setStatus(esc(t("locating")));
      navigator.geolocation.getCurrentPosition(function (pos) {
        var lat = pos.coords.latitude, lon = pos.coords.longitude;
        var origin = { lat: lat, lon: lon, label: lat.toFixed(5) + ", " + lon.toFixed(5), coarse: false };
        run(Promise.resolve(origin));
        reverse(lat, lon).then(function (label) {
          origin.label = label;
          if (state.origin === origin && state.results.length) renderResults();
        });
      }, function () { setStatus(esc(t("geoerr")), "error"); }, { enableHighAccuracy: true, timeout: 15000 });
    });
    $("lang").addEventListener("click", function () {
      state.lang = state.lang === "en" ? "bn" : "en";
      try { localStorage.setItem("lang", state.lang); } catch (e) {}
      renderText();
    });
    $("keyform").addEventListener("submit", function (e) {
      e.preventDefault();
      var k = $("keyinput").value.trim();
      if (!k) return;
      try { localStorage.setItem("geoapifyKey", k); } catch (err) {}
      location.reload();
    });
    if (!apiKey()) $("keybox").hidden = false;
    renderText();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
