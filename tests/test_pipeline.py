"""Offline regression tests with invented counts and no external services."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from business_demography.adapter import normalize_annual_response
from business_demography.decoder import DecodeError, Stream, decode
from business_demography.pipeline import main, run
from business_demography.validation import annual_summary, reconcile


def sample():
    return json.loads((ROOT / "data/sample/annual_counts.json").read_text(encoding="utf-8"))


def response_fixture():
    """Invent a hierarchical envelope to exercise descriptor-based aliases."""
    data = sample()
    selections = [{"Kind": 2, "Value": f"M{i}", "Subtotal": [f"A{i}", f"B{i}"]} for i in range(3)]
    groups = [{"G0": g["id"], "X": copy.deepcopy(g["cells"] + [g["total"]])} for g in data["groups"]]
    groups[0]["X"][0]["S"] = [{"N": f"M{i}"} for i in range(3)]
    groups[0]["X"][-1]["S"] = [{"N": f"B{i}"} for i in range(3)]
    totals = copy.deepcopy(data["annual_totals"] + [data["grand_total"]])
    totals[0]["S"] = [{"N": f"A{i}"} for i in range(3)]
    return {"results": [{"result": {"data": {
        "descriptor": {"Select": selections}, "dsr": {"DS": [{
            "SH": [{"DM2": [{"G1": y} for y in data["years"]]}],
            "PH": [{"DM0": [{"X": totals}]}, {"DM1": groups}]
        }]}}}}]}


class DecoderTests(unittest.TestCase):
    def test_every_repeat_mask_consumes_only_unset_slots(self):
        for mask in range(8):
            with self.subTest(mask=mask):
                stream = Stream(["balance", "closures", "openings"])
                stream.decode({"C": [10, 20, 30]})
                supplied = [100 + i for i in range(3) if not mask & (1 << i)]
                result = list(stream.decode({"C": supplied, "R": mask}).values())
                self.assertEqual([r.value for r in result],
                                 [10 * (i + 1) if mask & (1 << i) else 100 + i for i in range(3)])

    def test_cross_group_repeat_does_not_read_subtotal(self):
        rows = decode(sample())
        record = next(r for r in rows if r.group == "Group B" and r.year == 2021 and r.measure == "closures")
        self.assertEqual((record.value, record.status), (2, "repeated"))

    def test_subtotals_have_their_own_repeat_state(self):
        data = sample()
        data["groups"][1]["total"] = {"C": [-1, 9], "R": 2}
        row = next(r for r in decode(data) if r.group == "Group B" and r.kind == "group_total" and r.measure == "closures")
        self.assertEqual(row.value, 6)

    def test_explicit_null_is_not_zero(self):
        result = Stream(["balance", "closures", "openings"]).decode({"C": [0, None, 0]})
        self.assertEqual((result["closures"].value, result["closures"].status), (None, "unknown"))
        self.assertEqual(result["balance"].value, 0)

    def test_repeat_without_predecessor_is_unknown(self):
        result = Stream(["balance", "closures", "openings"]).decode({"C": [], "R": 7})
        self.assertTrue(all(v.value is None and v.status == "unknown" for v in result.values()))

    def test_suppression_survives_repeat(self):
        stream = Stream(["balance", "closures", "openings"])
        stream.decode({"C": [1, {"status": "suppressed"}, 2]})
        self.assertEqual(stream.decode({"C": [], "R": 7})["closures"].status, "suppressed")

    def test_absent_cell_invalidates_predecessor(self):
        stream = Stream(["balance", "closures", "openings"])
        stream.decode({"C": [1, 2, 3]})
        self.assertEqual(stream.decode(None)["balance"].status, "missing")
        self.assertIsNone(stream.decode({"C": [], "R": 7})["balance"].value)

    def test_schema_override_is_explicit_and_state_is_separate(self):
        stream = Stream(["balance", "closures", "openings"])
        stream.decode({"C": [5, 2, 7]})
        result = stream.decode({"S": ["openings", "balance", "closures"], "C": [9, 6, 3]})
        self.assertEqual(result["balance"].value, 6)
        self.assertEqual(stream.decode({"C": [], "R": 7})["balance"].value, 5)

    def test_rejects_ambiguous_or_invalid_cells(self):
        cases = [{"C": [1, 2]}, {"C": [], "R": 8}, {"C": [], "R": -1},
                 {"C": [1, 2, 3], "R": True}, {"C": [1.5, 2, 3]},
                 {"C": [True, 2, 3]}, {"C": [1, 2, 3], "extra": 2},
                 {"C": [1, 2, 3], "S": ["balance"]}]
        for cell in cases:
            with self.subTest(cell=cell), self.assertRaises(DecodeError):
                Stream(["balance", "closures", "openings"]).decode(cell)

    def test_duplicate_keys_and_misaligned_axes_rejected(self):
        for change in (lambda d: d["years"].reverse(),
                       lambda d: d["groups"].append(copy.deepcopy(d["groups"][0])),
                       lambda d: d["groups"][0]["cells"].pop(),
                       lambda d: d["annual_totals"].pop()):
            data = sample()
            change(data)
            with self.assertRaises(DecodeError):
                decode(data)


class ValidationTests(unittest.TestCase):
    def test_independent_fixture_reconciles(self):
        records = decode(sample())
        checks = reconcile(records)
        self.assertTrue(checks)
        self.assertTrue(all(c["status"] == "pass" for c in checks))
        self.assertEqual(len([r for r in records if r.kind == "detail"]), 27)

    def test_incorrect_control_fails_without_changing_data(self):
        data = sample()
        data["annual_totals"][0]["C"][0] += 1
        before = copy.deepcopy(data)
        checks = reconcile(decode(data))
        self.assertTrue(any(c["scope"] == "year" and c["residual"] == 1 for c in checks))
        self.assertEqual(data, before)

    def test_cancelling_year_errors_cannot_hide_in_grand_total(self):
        data = sample()
        data["annual_totals"][0]["C"][0] += 1
        data["annual_totals"][1]["C"][0] -= 1
        checks = reconcile(decode(data))
        self.assertEqual(sum(c["scope"] == "year" and c["status"] == "fail" for c in checks), 2)

    def test_missing_detail_does_not_pass_or_become_zero(self):
        data = sample()
        data["groups"][2]["cells"][0] = None
        records = decode(data)
        checks = reconcile(records)
        self.assertTrue(any(c["status"] == "incomplete" for c in checks))
        summary = annual_summary(records)
        self.assertTrue(all(r["value"] is None and r["unavailable_count"] == 1 for r in summary))

    def test_missing_control_is_incomplete(self):
        data = sample()
        data["grand_total"] = None
        self.assertTrue(any(c["scope"] == "detail_to_grand" and c["status"] == "incomplete"
                            for c in reconcile(decode(data))))

    def test_negative_balance_allowed_but_negative_event_counts_fail(self):
        data = sample()
        self.assertTrue(all(c["status"] == "pass" for c in reconcile(decode(data))))
        data["groups"][0]["cells"][0] = {"C": [5, -2, 3]}
        self.assertTrue(any(c["scope"] == "nonnegative_detail" for c in reconcile(decode(data))))

    def test_annual_summary_has_expected_business_values(self):
        summary = annual_summary(decode(sample()))
        values = {(r["year"], r["measure"]): r["value"] for r in summary}
        self.assertEqual(values[(2021, "openings")], 9)
        self.assertEqual(values[(2023, "balance")], 7)


class AdapterTests(unittest.TestCase):
    def test_descriptor_aliases_and_structure(self):
        mapping = {"M0": "balance", "M1": "closures", "M2": "openings"}
        normalized = normalize_annual_response(response_fixture(), mapping)
        self.assertEqual(decode(normalized), decode(sample()))

    def test_nonannual_or_nested_axis_rejected(self):
        for replacement in ({"G1": "2021 Q1"}, {"G1": 2021, "M": []}):
            fixture = response_fixture()
            fixture["results"][0]["result"]["data"]["dsr"]["DS"][0]["SH"][0]["DM2"][0] = replacement
            with self.assertRaises(DecodeError):
                normalize_annual_response(fixture, {"M0": "balance", "M1": "closures", "M2": "openings"})

    def test_mapping_must_be_complete(self):
        with self.assertRaises(DecodeError):
            normalize_annual_response(response_fixture(), {"M0": "balance"})


class PipelineTests(unittest.TestCase):
    def test_byte_reproducible_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            source = ROOT / "data/sample/annual_counts.json"
            report = run(source, first)
            self.assertEqual(report["validation_status"], "pass")
            run(source, second)
            self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()},
                             {p.name: p.read_bytes() for p in second.iterdir()})

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps(sample()), encoding="utf-8")
            args = ["--input", str(source), "--output", str(root / "result")]
            self.assertEqual(main(args), 0)
            data = sample()
            data["grand_total"] = None
            source.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(main(args), 2)
            data["grand_total"] = {"C": [99, 16, 32]}
            source.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(main(args), 2)
            source.write_text("not-json", encoding="utf-8")
            self.assertEqual(main(args), 1)


if __name__ == "__main__":
    unittest.main()
