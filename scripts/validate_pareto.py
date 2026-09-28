#!/usr/bin/env python3
"""Validate an authoritative Pareto set from representative three-axis scores."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--representatives", type=Path, required=True)
    parser.add_argument("--pareto", type=Path, required=True)
    parser.add_argument("--axes", nargs=3, default=["performance_deviation_score", "cost_deviation_score", "latency_deviation_score"])
    args = parser.parse_args()

    rows = read_rows(args.representatives)
    ids = [row.get("id") for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        print("FAIL: representative ids must be present and unique")
        return 1
    scores = {}
    errors = []
    for row in rows:
        try:
            values = tuple(float(row[axis]) for axis in args.axes)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{row.get('id')}: invalid axis value ({exc})")
            continue
        nonfinite_axes = [axis for axis, value in zip(args.axes, values) if not math.isfinite(value)]
        if nonfinite_axes:
            errors.append(f"{row.get('id')}: non-finite axis value(s): {', '.join(nonfinite_axes)}")
            continue
        scores[row["id"]] = values
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    expected = set()
    for candidate_id, candidate in scores.items():
        dominated = False
        for other_id, other in scores.items():
            if other_id == candidate_id:
                continue
            at_least_as_good = all(other[index] >= candidate[index] for index in range(3))
            strictly_better = any(other[index] > candidate[index] for index in range(3))
            if at_least_as_good and strictly_better:
                dominated = True
                break
        if not dominated:
            expected.add(candidate_id)

    declared = read_json(args.pareto)
    if isinstance(declared, dict):
        declared = declared.get("pareto_ids", declared.get("ids", []))
    declared_set = set(declared)
    if declared_set != expected:
        print(f"FAIL: Pareto mismatch; missing={sorted(expected - declared_set)}, extra={sorted(declared_set - expected)}")
        return 1
    print(f"PASS: {len(expected)} three-axis Pareto candidates validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
