// Classifier tests on the shared expectations in tests/classify_cases.json (also used by the Python tests).
// Run: node --test tests/classify.test.js
const test = require("node:test");
const assert = require("node:assert");
const rules = require("../docs/app/facility_rules.json");
const { classify } = require("../docs/app/classify.js");
const cases = require("./classify_cases.json");

for (const c of cases) {
  test(`${c.ed}${c.speciality ? "/" + c.speciality : ""}: ${c.name}`, () => {
    const r = classify(rules, { name: c.name, nameEn: c.nameEn, tags: c.tags });
    assert.strictEqual(r.ed, c.ed, r.reasons.join("; "));
    assert.strictEqual(r.speciality, c.speciality, r.reasons.join("; "));
  });
}
