// Tests for the web app's pure helpers. Run: node --test tests/
const test = require("node:test");
const assert = require("node:assert");
const app = require("../docs/app/app.js");

test("haversine: Dhaka Zero Point to Shahbag is about 1.6 to 2.3 km", () => {
  const d = app.haversineM(23.7270, 90.4125, 23.7380, 90.3958);
  assert.ok(d > 1500 && d < 2300, String(d));
});

test("hospital-tagged diagnostic centres and eye hospitals are flagged", () => {
  const hosp = ["healthcare", "healthcare.hospital"];
  assert.ok(app.maybeNotER("Al Fateh Diagnostics", hosp));
  assert.ok(app.maybeNotER("Ispahani Islamia Eye Institute and Hospital", hosp));
  assert.ok(!app.maybeNotER("Shahbagh P.G. Hospital", hosp));
  assert.ok(!app.maybeNotER("Ahammed Pharma", ["healthcare.pharmacy"]));
});

test("city-level geocoding fallback is detected (API spelling: disrict)", () => {
  assert.ok(app.isCoarse({ rank: { match_type: "match_by_city_or_disrict" } }));
  assert.ok(!app.isCoarse({ rank: { match_type: "full_match" } }));
  assert.ok(!app.isCoarse({}));
});

test("ranking is by travel time, unreachable last", () => {
  const out = app.rankByTime([{ n: "A", time: 900 }, { n: "B", time: null }, { n: "C", time: 120 }]);
  assert.deepStrictEqual(out.map((x) => x.n), ["C", "A", "B"]);
});

test("categories match the CLI", () => {
  assert.strictEqual(app.CATEGORIES.fire, "service.fire_station");
  assert.strictEqual(app.CATEGORIES.ambulance, "emergency.ambulance_station");
});

test("near-duplicate places are merged, different places kept", () => {
  const out = app.dedupe([
    { name: "radda", lat: 23.80756, lon: 90.36969 },
    { name: "RADDA", lat: 23.80755, lon: 90.36976 },
    { name: "Radda MCH-FP Centre", lat: 23.80735, lon: 90.37003 },
    { name: "radda", lat: 23.8200, lon: 90.3800 },
  ]);
  assert.deepStrictEqual(out.map((x) => x.name), ["radda", "Radda MCH-FP Centre", "radda"]);
});

test("a mosque tagged as a fire station is flagged as a different place", () => {
  assert.ok(app.maybeOtherPlace("Mosque of Bangladesh Fire Service & Civil Defence Headquarter"));
  assert.ok(app.maybeOtherPlace("বায়তুল মোকাররম মসজিদ"));
  assert.ok(!app.maybeOtherPlace("Lalbagh Fire Station"));
  assert.ok(!app.maybeOtherPlace("Fire Service & Civil Defence Headquarter"));
});
