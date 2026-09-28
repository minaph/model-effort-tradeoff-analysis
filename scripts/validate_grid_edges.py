#!/usr/bin/env python3
"""Validate fixed model×effort adjacency and direction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--edges", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mds-edges", type=Path, help="optional MDS edge JSON; every edge must reuse a validated grid edge")
    args = parser.parse_args()
    source = read_json(args.input)
    config = read_json(args.config)
    points = {point["id"]: point for point in source["points"]}
    model_order = {model: index for index, model in enumerate(config["model_order"])}
    effort_order = {effort: index for index, effort in enumerate(config["effort_order"])}
    expected: dict[frozenset[str], tuple[str, bool]] = {}
    for point in points.values():
        for other in points.values():
            if point["id"] >= other["id"]:
                continue
            same_model = point["model"] == other["model"]
            same_effort = point["effort"] == other["effort"]
            adjacent_effort = same_model and abs(effort_order[point["effort"]] - effort_order[other["effort"]]) == 1
            adjacent_model = same_effort and abs(model_order[point["model"]] - model_order[other["model"]]) == 1
            if not (adjacent_effort or adjacent_model):
                continue
            if adjacent_effort:
                first, second = sorted((point, other), key=lambda item: effort_order[item["effort"]])
                edge_type = "effort"
            else:
                first, second = sorted((point, other), key=lambda item: model_order[item["model"]])
                edge_type = "model"
            boundary_pairs = {tuple(pair) for pair in config.get("boundary_model_pairs", [])}
            boundary = edge_type == "model" and (first["model"], second["model"]) in boundary_pairs
            expected[frozenset((first["id"], second["id"]))] = (edge_type, boundary)

    edges = read_json(args.edges).get("edges", [])
    seen: set[frozenset[str]] = set()
    errors: list[str] = []
    for index, edge in enumerate(edges):
        source_id, target_id = edge.get("from"), edge.get("to")
        key = frozenset((source_id, target_id))
        if source_id not in points or target_id not in points:
            errors.append(f"edge[{index}] has an unknown endpoint")
            continue
        if key in seen:
            errors.append(f"edge[{index}] duplicates an undirected pair")
        seen.add(key)
        if key not in expected:
            errors.append(f"edge[{index}] is not an adjacent grid pair")
            continue
        expected_type, expected_boundary = expected[key]
        if edge.get("type") != expected_type:
            errors.append(f"edge[{index}] type is {edge.get('type')!r}, expected {expected_type!r}")
        if bool(edge.get("boundary", False)) != expected_boundary:
            errors.append(f"edge[{index}] boundary flag is inconsistent")
        first_index = effort_order[points[source_id]["effort"]] if expected_type == "effort" else model_order[points[source_id]["model"]]
        target_index = effort_order[points[target_id]["effort"]] if expected_type == "effort" else model_order[points[target_id]["model"]]
        if target_index <= first_index:
            errors.append(f"edge[{index}] direction does not move forward in fixed order")
    missing = set(expected) - seen
    if missing:
        errors.append(f"missing {len(missing)} expected adjacent edges")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    if args.mds_edges:
        mds_edges = read_json(args.mds_edges).get("edges", [])
        grid_by_pair = {frozenset((edge["from"], edge["to"])): edge for edge in edges}
        fit_ids = set(config.get("mds", {}).get("fit_ids", []))
        allow_boundary = bool(config.get("mds", {}).get("include_boundary_edges", False))
        mds_seen: set[frozenset[str]] = set()
        for index, edge in enumerate(mds_edges):
            source_id, target_id = edge.get("from"), edge.get("to")
            key = frozenset((source_id, target_id))
            if key in mds_seen:
                errors.append(f"MDS edge[{index}] duplicates an undirected pair")
                continue
            mds_seen.add(key)
            grid_edge = grid_by_pair.get(key)
            if grid_edge is None:
                errors.append(f"MDS edge[{index}] is not a grid edge")
                continue
            if source_id not in fit_ids or target_id not in fit_ids:
                errors.append(f"MDS edge[{index}] has an endpoint outside the MDS fit")
            if (source_id, target_id) != (grid_edge.get("from"), grid_edge.get("to")):
                errors.append(f"MDS edge[{index}] reverses the fixed grid direction")
            if bool(grid_edge.get("boundary", False)) and not allow_boundary:
                errors.append(f"MDS edge[{index}] includes a boundary edge while include_boundary_edges is false")
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            return 1
    suffix = f"; {len(mds_edges)} MDS edges reused" if args.mds_edges else ""
    print(f"PASS: {len(edges)} fixed adjacent edges validated{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
