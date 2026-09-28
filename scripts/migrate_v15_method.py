#!/usr/bin/env python3
"""Migrate the legacy v15 method JSON into the structured method schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="legacy v15 method JSON; never modified")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    legacy = read_json(args.input)
    required = {"selected_benchmarks", "excluded_benchmarks", "model_order", "effort_order", "mds"}
    missing = required - set(legacy)
    if missing:
        raise ValueError(f"not a recognized legacy v15 method file; missing {sorted(missing)}")
    old_mds = legacy["mds"]
    fit_ids = list(old_mds.get("mds_fit_ids", old_mds.get("fit_ids", [])))
    excluded_ids = list(old_mds.get("excluded_from_mds_ids", old_mds.get("excluded_ids", [])))
    projection_ids = list(old_mds.get("projection_only_ids", []))
    models = set(legacy["model_order"])
    boundary = []
    if {"GPT-5.5", "GPT-5.6 Luna"} <= models:
        boundary.append(["GPT-5.5", "GPT-5.6 Luna"])

    migrated = {
        "version": legacy.get("version", "v15") + "-structured",
        "analysis_mode": "three_axis_v15",
        "selected_benchmarks": list(legacy["selected_benchmarks"]),
        "excluded_benchmarks": list(legacy["excluded_benchmarks"]),
        "model_order": list(legacy["model_order"]),
        "effort_order": list(legacy["effort_order"]),
        "metrics": {
            "performance": {"field": "performance", "direction": 1},
            "cost": {"field": "cost", "direction": -1},
            "latency": {"field": "latency_min", "direction": -1}
        },
        "standardization": {"scope": "within_benchmark", "sd": "population", "log_transform": False},
        "missing_value_policy": "error",
        "representative": "median",
        "display_transform": "50 + 10z",
        "variability": {"metric": "performance", "stat": "population_sd", "display_scale": 10},
        "adjustments": [
            {"model": "GPT-5.6 Luna", "metric": "cost", "multiplier": 0.2, "mode": "normal", "source_url": None, "provenance_status": "needs_source_url_review"},
            {"model": "GPT-5.6 Terra", "metric": "cost", "multiplier": 0.8, "mode": "normal", "source_url": None, "provenance_status": "needs_source_url_review"}
        ],
        "non_applied_interventions": [
            {"model": "GPT-5.6 Sol", "metric": "latency", "mode": "fast", "applied": False, "reason": "The claim is Fast-mode only; it is not applied to normal-mode latency, which remains unchanged.", "source_url": None, "provenance_status": "needs_source_url_review"}
        ],
        "pareto": {"axes": ["performance", "cost", "latency"], "authoritative": True},
        "boundary_model_pairs": boundary,
        "mds": {
            "fit_ids": fit_ids,
            "anchor_ids": [candidate_id for candidate_id in fit_ids if candidate_id == "GPT-5.6 Sol|max"],
            "expected_pareto_count": 14,
            "excluded_model_names": ["GPT-5.5"] if "GPT-5.5" in models else [],
            "excluded_ids": excluded_ids,
            "projection_only_ids": projection_ids,
            "fit_count": len(fit_ids),
            "projection_only_count": len(projection_ids),
            "edge_source": "grid_adjacency",
            "distance_method": "metric_mds",
            "algorithm": "v15_smacof_circle",
            "iterations": 2400,
            "tolerance": 1e-13,
            "distance_space": "internal_z",
            "stress_definition": "sqrt(sum of squared pairwise distance residuals)",
            "relative_rmse_definition": "sqrt(sum residuals squared) / sqrt(sum target distances squared)",
            "distance_axes": ["performance_z_median", "cost_z_median", "latency_z_median"],
            "display_rotation": "post_fit_only",
            "include_boundary_edges": False
        },
        "migration": {
            "source_legacy_method": str(args.input),
            "legacy_keys_preserved": sorted(legacy.keys()),
            "provenance_warning": "Legacy method JSON did not carry adjustment source URLs/dates; fill and review them before release."
        }
    }
    args.output.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "fit_count": len(fit_ids), "projection_only_count": len(projection_ids)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
