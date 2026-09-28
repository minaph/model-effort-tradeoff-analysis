#!/usr/bin/env python3
"""Validate MDS fit/exclusion/projection lists and optional coordinate pairs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


V15_MDS_PROTOCOL = {
    "algorithm": "v15_smacof_circle",
    "iterations": 2400,
    "tolerance": 1e-13,
    "distance_space": "internal_z",
    "stress_definition": "sqrt(sum of squared pairwise distance residuals)",
    "relative_rmse_definition": "sqrt(sum residuals squared) / sqrt(sum target distances squared)",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def ids_from_object(value):
    if isinstance(value, dict):
        if "coordinates" in value:
            value = value["coordinates"]
        elif "points" in value:
            value = value["points"]
    if not isinstance(value, list):
        raise ValueError("expected a list or an object containing coordinates/points")
    ids = []
    for item in value:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict) and item.get("id"):
            if "x" in item and "y" in item:
                try:
                    if not math.isfinite(float(item["x"])) or not math.isfinite(float(item["y"])):
                        raise ValueError
                except (TypeError, ValueError):
                    raise ValueError("coordinate x/y values must be finite")
            ids.append(item["id"])
        else:
            raise ValueError("coordinate entries must be ids or objects with id")
    return ids


def pareto_ids_from_rows(rows, axes):
    values = {}
    for candidate_id, row in rows.items():
        try:
            values[candidate_id] = [float(row[axis]) for axis in axes]
        except (KeyError, TypeError, ValueError):
            continue
    pareto = set()
    for candidate_id, candidate_values in values.items():
        if not any(
            other_id != candidate_id
            and all(other_values[index] >= candidate_values[index] for index in range(len(axes)))
            and any(other_values[index] > candidate_values[index] for index in range(len(axes)))
            for other_id, other_values in values.items()
        ):
            pareto.add(candidate_id)
    return pareto


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mds", type=Path, help="optional compute_mds.py output to validate")
    parser.add_argument("--representatives", type=Path, help="representative CSV for independent distance/stress recomputation")
    parser.add_argument("--coordinates", type=Path)
    parser.add_argument("--shepard", type=Path)
    args = parser.parse_args()

    source = read_json(args.input)
    config = read_json(args.config)
    analysis_mode = config.get("analysis_mode")
    known = {point["id"] for point in source.get("points", [])}
    mds = config.get("mds", {})
    fit = list(mds.get("fit_ids", []))
    excluded = list(mds.get("excluded_ids", []))
    projection = list(mds.get("projection_only_ids", []))
    errors = []
    if "analysis_mode" not in config:
        errors.append("missing required analysis_mode")
    elif analysis_mode not in {"three_axis_v15", "three_axis_generic", "reduced_2d"}:
        errors.append(f"unknown analysis_mode: {analysis_mode!r}")
    groups = {"fit": fit, "excluded": excluded, "projection_only": projection}
    for name, ids in groups.items():
        if len(ids) != len(set(ids)):
            errors.append(f"{name} contains duplicate ids")
        unknown = set(ids) - known
        if unknown:
            errors.append(f"{name} contains unknown ids: {sorted(unknown)}")
    if set(fit) & set(excluded) or set(fit) & set(projection) or set(excluded) & set(projection):
        errors.append("fit, excluded, and projection-only sets overlap")
    if mds.get("projection_only_count") is not None and mds["projection_only_count"] != len(projection):
        errors.append("projection_only_count does not match projection_only_ids")
    if analysis_mode == "reduced_2d" and (fit or excluded or projection):
        errors.append("reduced_2d must not contain an MDS fit, excluded set, or projection-only set")
    if mds.get("fit_count") is not None and mds["fit_count"] != len(fit):
        errors.append("fit_count does not match fit_ids")

    if args.coordinates:
        coordinate_ids = ids_from_object(read_json(args.coordinates))
        if set(coordinate_ids) != set(fit):
            errors.append("coordinate ids do not exactly match MDS fit_ids")
    if args.mds:
        mds_output = read_json(args.mds)
        if not args.representatives:
            errors.append("--representatives is required when validating an MDS output")
        else:
            representative_rows = read_rows(args.representatives)
            representative_kind = config.get("representative", "median")
            expected_axes = [f"{metric}_z_{representative_kind}" for metric in ("performance", "cost", "latency")]
            protocol_missing = [key for key in V15_MDS_PROTOCOL if key not in mds]
            if protocol_missing:
                errors.append(f"three_axis_v15 MDS config is missing protocol keys: {protocol_missing}")
            configured_axes = list(mds.get("distance_axes", []))
            axes = list(mds_output.get("distance_axes", []))
            if configured_axes != expected_axes:
                errors.append("config mds.distance_axes must be the three internal representative z columns")
            if axes != configured_axes:
                errors.append("MDS output distance_axes do not match config mds.distance_axes")
            if analysis_mode == "three_axis_v15":
                if len(source.get("points", [])) != 19 or len(config.get("selected_benchmarks", [])) != 7:
                    errors.append("three_axis_v15 requires 19 candidates and seven selected benchmarks")
                pareto_ids = pareto_ids_from_rows(representative_rows, expected_axes)
                anchor_ids = mds.get("anchor_ids")
                excluded_model_names = mds.get("excluded_model_names")
                if not isinstance(anchor_ids, list) or not anchor_ids:
                    errors.append("three_axis_v15 MDS must declare non-empty anchor_ids")
                    anchor_ids = []
                if not isinstance(excluded_model_names, list) or not excluded_model_names:
                    errors.append("three_axis_v15 MDS must declare excluded_model_names")
                    excluded_model_names = []
                if mds.get("expected_pareto_count") != 14 or len(pareto_ids) != 14:
                    errors.append("three_axis_v15 requires an independently recomputed 14-point Pareto set")
                expected_fit = pareto_ids | set(anchor_ids)
                expected_excluded = {point.get("id") for point in source.get("points", []) if point.get("model") in set(excluded_model_names)}
                if set(anchor_ids) & pareto_ids:
                    errors.append("three_axis_v15 MDS anchors must be distinct from the Pareto set")
                if set(fit) != expected_fit:
                    errors.append("three_axis_v15 MDS fit_ids must equal Pareto ids union anchor_ids")
                if set(excluded) != expected_excluded or set(excluded) != known - expected_fit:
                    errors.append("three_axis_v15 MDS excluded_ids must be the declared excluded model set and complement the fit")
                if projection:
                    errors.append("three_axis_v15 MDS projection_only_ids must be empty")
                if len(expected_fit) != 15:
                    errors.append("three_axis_v15 MDS fit must contain 15 candidates")
            if mds_output.get("distance_space") != mds.get("distance_space") or mds_output.get("distance_space") != "internal_z":
                errors.append("MDS output distance_space must be explicitly internal_z and match config")
            for key, expected in V15_MDS_PROTOCOL.items():
                if key not in mds or mds.get(key) != expected:
                    errors.append(f"config MDS {key} does not match the fixed v15 protocol")
                if key != "iterations" and mds_output.get(key) != expected:
                    errors.append(f"MDS output {key} does not match the fixed v15 protocol")
            if mds_output.get("max_iterations") != V15_MDS_PROTOCOL["iterations"]:
                errors.append("MDS output max_iterations does not match config iterations")
            try:
                used_iterations = int(mds_output.get("iterations"))
                if not 1 <= used_iterations <= V15_MDS_PROTOCOL["iterations"]:
                    errors.append("MDS output iterations must be within the configured v15 limit")
            except (TypeError, ValueError):
                errors.append("MDS output iterations must be an integer")
            if list(mds_output.get("fit_ids", [])) != list(mds.get("fit_ids", [])):
                errors.append("MDS output fit_ids do not match config")
            if set(mds_output.get("excluded_ids", [])) != set(mds.get("excluded_ids", [])):
                errors.append("MDS output excluded_ids do not match config")
            if set(mds_output.get("projection_only_ids", [])) != set(mds.get("projection_only_ids", [])):
                errors.append("MDS output projection_only_ids do not match config")
            missing_reps = set(fit) - set(representative_rows)
            if missing_reps:
                errors.append(f"representatives lack MDS fit ids: {sorted(missing_reps)}")
            coordinate_rows = {item.get("id"): item for item in mds_output.get("coordinates", []) if isinstance(item, dict)}
            if set(coordinate_rows) != set(fit):
                errors.append("MDS coordinates do not exactly match fit ids for distance recomputation")
            pair_rows = {}
            for pair in mds_output.get("pairs", []):
                if isinstance(pair, dict) and "a" in pair and "b" in pair:
                    pair_rows[frozenset((pair["a"], pair["b"]))] = pair
            computed_residuals = []
            computed_targets = []
            for left_index, left_id in enumerate(fit):
                for right_id in fit[left_index + 1:]:
                    if left_id not in representative_rows or right_id not in representative_rows or left_id not in coordinate_rows or right_id not in coordinate_rows:
                        continue
                    try:
                        original = math.sqrt(sum((float(representative_rows[left_id][axis]) - float(representative_rows[right_id][axis])) ** 2 for axis in expected_axes))
                        left_coordinate = coordinate_rows[left_id]
                        right_coordinate = coordinate_rows[right_id]
                        embedded = math.hypot(float(left_coordinate["x"]) - float(right_coordinate["x"]), float(left_coordinate["y"]) - float(right_coordinate["y"]))
                    except (KeyError, TypeError, ValueError):
                        errors.append(f"unable to recompute MDS pair {left_id} / {right_id}")
                        continue
                    computed_targets.append(original)
                    computed_residuals.append(embedded - original)
                    declared = pair_rows.get(frozenset((left_id, right_id)))
                    try:
                        declared_original = float(declared.get("original_distance", float("nan"))) if declared else float("nan")
                        declared_embedded = float(declared.get("mds_distance", float("nan"))) if declared else float("nan")
                    except (TypeError, ValueError):
                        declared_original = declared_embedded = float("nan")
                    if not declared or not math.isclose(declared_original, original, rel_tol=1e-8, abs_tol=1e-8) or not math.isclose(declared_embedded, embedded, rel_tol=1e-8, abs_tol=1e-8):
                        errors.append(f"MDS pair distance mismatch for {left_id} / {right_id}")
            if computed_residuals:
                recomputed_stress = math.sqrt(sum(value * value for value in computed_residuals))
                target_sum = sum(value * value for value in computed_targets)
                recomputed_relative_rmse = recomputed_stress / math.sqrt(target_sum) if target_sum else 0.0
                if not math.isclose(float(mds_output.get("stress", float("nan"))), recomputed_stress, rel_tol=1e-8, abs_tol=1e-8):
                    errors.append("MDS stress does not match coordinates and representative distances")
                if not math.isclose(float(mds_output.get("relative_rmse", float("nan"))), recomputed_relative_rmse, rel_tol=1e-8, abs_tol=1e-8):
                    errors.append("MDS relative_rmse does not match coordinates and representative distances")
        coordinate_ids = ids_from_object(mds_output)
        if set(coordinate_ids) != set(fit):
            errors.append("MDS output coordinate ids do not exactly match MDS fit_ids")
        for key in ("stress", "relative_rmse"):
            value = mds_output.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
                errors.append(f"MDS output {key} must be a finite nonnegative number")
        if mds_output.get("pair_count") != len(fit) * (len(fit) - 1) // 2:
            errors.append("MDS output pair_count does not match the complete fit-pair count")
        pairs = mds_output.get("pairs", [])
        pair_keys = set()
        if len(pairs) != len(fit) * (len(fit) - 1) // 2:
            errors.append("MDS output pairs do not contain the complete fit-pair count")
        for index, pair in enumerate(pairs):
            if not isinstance(pair, dict) or not {"a", "b", "original_distance", "mds_distance"} <= pair.keys():
                errors.append(f"MDS output pair[{index}] lacks ids or distances")
                continue
            key = frozenset((pair["a"], pair["b"]))
            if pair["a"] not in fit or pair["b"] not in fit or pair["a"] == pair["b"]:
                errors.append(f"MDS output pair[{index}] is outside the fit or self-referential")
            if key in pair_keys:
                errors.append(f"MDS output pair[{index}] duplicates a pair")
            pair_keys.add(key)
            for distance_key in ("original_distance", "mds_distance"):
                try:
                    distance = float(pair[distance_key])
                except (TypeError, ValueError):
                    distance = float("nan")
                if not math.isfinite(distance) or distance < 0:
                    errors.append(f"MDS output pair[{index}] has invalid {distance_key}")
    if args.shepard:
        shepard = read_json(args.shepard)
        if isinstance(shepard, dict):
            shepard = shepard.get("pairs", shepard.get("shepard", []))
        if not isinstance(shepard, list):
            errors.append("Shepard data must be a list or an object containing pairs/shepard")
        else:
            expected_pairs = len(fit) * (len(fit) - 1) // 2
            if len(shepard) != expected_pairs:
                errors.append(f"Shepard pair count is {len(shepard)}, expected {expected_pairs}")
            for index, pair in enumerate(shepard):
                if not isinstance(pair, dict) or not {"a", "b"} <= pair.keys():
                    errors.append(f"Shepard pair[{index}] lacks a/b ids")
                    continue
                if pair["a"] not in fit or pair["b"] not in fit or pair["a"] == pair["b"]:
                    errors.append(f"Shepard pair[{index}] is outside the MDS fit or self-referential")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: MDS scope validated for {len(fit)} fit, {len(excluded)} excluded, {len(projection)} projection-only candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
