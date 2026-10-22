"""Python classifier on the same expectations as tests/classify.test.js (keeps the two ports in step)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dhaka_emergency.classify import classify  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "classify_cases.json"), encoding="utf-8") as fh:
    CASES = json.load(fh)


class ClassifyTests(unittest.TestCase):
    def test_shared_cases(self):
        for c in CASES:
            with self.subTest(name=c["name"]):
                r = classify({"name": c["name"], "nameEn": c["nameEn"], "tags": c["tags"]})
                self.assertEqual((r["ed"], r["speciality"], r["major"]), (c["ed"], c["speciality"], c["major"]),
                                 "; ".join(r["reasons"]))


if __name__ == "__main__":
    unittest.main()
