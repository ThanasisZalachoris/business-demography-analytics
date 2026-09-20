"""Deterministic offline CSV/JSON outputs and a validation-aware CLI."""

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .decoder import DecodeError, decode
from .validation import annual_summary, reconcile


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(input_path, output_dir):
    raw = Path(input_path).read_bytes()
    payload = json.loads(raw)
    records = decode(payload)
    checks = reconcile(records)
    statuses = {s: sum(c["status"] == s for c in checks) for s in ("pass", "fail", "incomplete")}
    overall = "fail" if statuses["fail"] else "incomplete" if statuses["incomplete"] else "pass"
    report = {"schema_version": 1, "input_sha256": hashlib.sha256(raw).hexdigest(),
              "detail_records": sum(r.kind == "detail" for r in records),
              "groups": len(payload["groups"]), "years": payload["years"],
              "validation_status": overall, "checks": statuses}
    output = Path(output_dir)
    if output.resolve() == Path(input_path).resolve() or output.resolve() in Path(input_path).resolve().parents:
        raise ValueError("Output directory must be separate from input data")
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "annual_detail.csv", [asdict(r) for r in records if r.kind == "detail"])
    write_csv(output / "declared_totals.csv", [asdict(r) for r in records if r.kind != "detail"])
    write_csv(output / "annual_summary.csv", annual_summary(records))
    write_csv(output / "reconciliation.csv", checks)
    (output / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Decode and validate annual business counts offline")
    parser.add_argument("--input", type=Path, default=Path("data/sample/annual_counts.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/sample"))
    args = parser.parse_args(argv)
    try:
        report = run(args.input, args.output)
    except (DecodeError, ValueError, OSError) as exc:
        # Avoid printing transport data or local paths in generated artifacts.
        print("Pipeline error: " + type(exc).__name__)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report["validation_status"] == "pass" else 2
