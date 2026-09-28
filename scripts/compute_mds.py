#!/usr/bin/env python3
"""Compute v15-compatible metric MDS coordinates and Shepard diagnostics."""

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


def metric_mds(features: list[list[float]], iterations: int, tolerance: float):
    """Port the v15 circle-initialized SMACOF loop without a library random seed."""
    count = len(features)
    coordinates = [[math.cos(2 * math.pi * index / count), math.sin(2 * math.pi * index / count)] for index in range(count)]
    targets = [[0.0] * count for _ in range(count)]
    for left in range(count):
        for right in range(left + 1, count):
            target = math.sqrt(sum((features[left][axis] - features[right][axis]) ** 2 for axis in range(3)))
            targets[left][right] = targets[right][left] = target
    last_loss = float("inf")
    used_iterations = 0
    for iteration in range(iterations):
        b = [[0.0] * count for _ in range(count)]
        for left in range(count):
            for right in range(left + 1, count):
                current = math.hypot(coordinates[left][0] - coordinates[right][0], coordinates[left][1] - coordinates[right][1]) or 1e-9
                weight = targets[left][right] / current
                b[left][right] = b[right][left] = -weight
                b[left][left] += weight
                b[right][right] += weight
        next_coordinates = []
        for left in range(count):
            next_coordinates.append([
                sum(b[left][index] * coordinates[index][0] for index in range(count)) / count,
                sum(b[left][index] * coordinates[index][1] for index in range(count)) / count,
            ])
        center_x = sum(value[0] for value in next_coordinates) / count
        center_y = sum(value[1] for value in next_coordinates) / count
        coordinates = [[value[0] - center_x, value[1] - center_y] for value in next_coordinates]
        loss = 0.0
        for left in range(count):
            for right in range(left + 1, count):
                delta = math.hypot(coordinates[left][0] - coordinates[right][0], coordinates[left][1] - coordinates[right][1]) - targets[left][right]
                loss += delta * delta
        used_iterations = iteration + 1
        if abs(last_loss - loss) < tolerance:
            last_loss = loss
            break
        last_loss = loss
    squared_target = sum(targets[left][right] ** 2 for left in range(count) for right in range(left + 1, count))
    stress = math.sqrt(last_loss)
    relative_rmse = stress / math.sqrt(squared_target) if squared_target else 0.0
    return coordinates, targets, stress, relative_rmse, used_iterations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--representatives", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--axes", nargs=3, default=None, help="three internal representative columns; defaults to the z-space medians")
    args = parser.parse_args()

    config = read_json(args.config)
    if "analysis_mode" not in config:
        raise ValueError("missing required analysis_mode")
    analysis_mode = config["analysis_mode"]
    if analysis_mode == "reduced_2d":
        raise ValueError("compute_mds.py is not available for the reduced_2d branch")
    if analysis_mode not in {"three_axis_v15", "three_axis_generic"}:
        raise ValueError(f"unsupported analysis_mode for MDS: {analysis_mode}")
    rows = {row["id"]: row for row in read_rows(args.representatives)}
    mds_config = config.get("mds", {})
    fit_ids = list(mds_config.get("fit_ids", []))
    excluded_ids = set(mds_config.get("excluded_ids", []))
    projection_ids = set(mds_config.get("projection_only_ids", []))
    if len(fit_ids) != len(set(fit_ids)):
        raise ValueError("MDS fit_ids must be unique")
    if set(fit_ids) & excluded_ids or set(fit_ids) & projection_ids or excluded_ids & projection_ids:
        raise ValueError("MDS fit, excluded, and projection-only ids overlap")
    unknown = (set(fit_ids) | excluded_ids | projection_ids) - set(rows)
    if unknown:
        raise ValueError(f"MDS references unknown representative ids: {sorted(unknown)}")
    if not fit_ids:
        raise ValueError("MDS fit_ids must not be empty")
    protocol_keys = ["algorithm", "iterations", "tolerance", "distance_space", "stress_definition", "relative_rmse_definition", "distance_axes"]
    missing_protocol_keys = [key for key in protocol_keys if key not in mds_config]
    if missing_protocol_keys:
        raise ValueError(f"{analysis_mode} MDS config is missing protocol keys: {missing_protocol_keys}")
    representative_kind = config.get("representative", "median")
    configured_axes = list(mds_config["distance_axes"])
    expected_axes = [f"{metric}_z_{representative_kind}" for metric in ("performance", "cost", "latency")]
    if mds_config["distance_space"] != "internal_z" or configured_axes != expected_axes:
        raise ValueError(f"{analysis_mode} MDS must use the configured internal representative z columns")
    if args.axes and list(args.axes) != configured_axes:
        raise ValueError("--axes must exactly match mds.distance_axes; use the method config as the geometry contract")
    axes = configured_axes
    if len(axes) != 3:
        raise ValueError("MDS distance_axes must contain exactly three representative columns")
    try:
        features = [[float(rows[candidate_id][axis]) for axis in axes] for candidate_id in fit_ids]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid MDS representative value: {exc}")
    if not all(math.isfinite(value) for row in features for value in row):
        raise ValueError("MDS representative values must be finite")

    algorithm = mds_config["algorithm"]
    if algorithm != "v15_smacof_circle":
        raise ValueError("this bundled calculator supports only algorithm=v15_smacof_circle")
    try:
        iterations = int(mds_config["iterations"])
        tolerance = float(mds_config["tolerance"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid v15 MDS protocol value: {exc}")
    if iterations != 2400 or not math.isclose(tolerance, 1e-13, rel_tol=0.0, abs_tol=0.0):
        raise ValueError(f"{analysis_mode} MDS uses the fixed v15 MDS protocol: 2400 iterations and tolerance 1e-13")
    if mds_config["stress_definition"] != "sqrt(sum of squared pairwise distance residuals)":
        raise ValueError("unsupported stress_definition for the bundled v15 MDS calculator")
    if mds_config["relative_rmse_definition"] != "sqrt(sum residuals squared) / sqrt(sum target distances squared)":
        raise ValueError("unsupported relative_rmse_definition for the bundled v15 MDS calculator")
    coordinates, target_distances, stress, relative_rmse, used_iterations = metric_mds(features, iterations, tolerance)

    angle = float(mds_config.get("display_rotation_radians", 0.0))
    if not math.isfinite(angle):
        raise ValueError("display_rotation_radians must be finite")
    if angle:
        cos_angle, sin_angle = math.cos(angle), math.sin(angle)
        coordinates = [[value[0] * cos_angle - value[1] * sin_angle, value[0] * sin_angle + value[1] * cos_angle] for value in coordinates]

    pairs = []
    for left in range(len(fit_ids)):
        for right in range(left + 1, len(fit_ids)):
            pairs.append({
                "a": fit_ids[left],
                "b": fit_ids[right],
                "original_distance": target_distances[left][right],
                "mds_distance": math.hypot(coordinates[left][0] - coordinates[right][0], coordinates[left][1] - coordinates[right][1]),
            })
    result = {
        "fit_ids": fit_ids,
        "excluded_ids": sorted(excluded_ids),
        "projection_only_ids": sorted(projection_ids),
        "coordinates": [{"id": candidate_id, "x": coordinates[index][0], "y": coordinates[index][1]} for index, candidate_id in enumerate(fit_ids)],
        "pairs": pairs,
        "stress": stress,
        "relative_rmse": relative_rmse,
        "pair_count": len(pairs),
        "iterations": used_iterations,
        "max_iterations": iterations,
        "tolerance": tolerance,
        "algorithm": algorithm,
        "stress_definition": mds_config["stress_definition"],
        "relative_rmse_definition": mds_config["relative_rmse_definition"],
        "distance_space": mds_config["distance_space"],
        "distance_axes": axes,
        "distance_method": "metric_mds",
        "display_rotation_radians": angle,
        "edge_source": mds_config.get("edge_source", "grid_adjacency"),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fit_count": len(fit_ids), "pair_count": len(pairs), "stress": stress, "relative_rmse": relative_rmse, "iterations": used_iterations}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
