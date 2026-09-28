#!/usr/bin/env python3
"""Validate the non-visual parts of a model×effort analysis contract."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import date
from pathlib import Path
from statistics import median
from urllib.parse import urlparse


V15_MDS_PROTOCOL = {
    "algorithm": "v15_smacof_circle",
    "iterations": 2400,
    "tolerance": 1e-13,
    "distance_space": "internal_z",
    "stress_definition": "sqrt(sum of squared pairwise distance residuals)",
    "relative_rmse_definition": "sqrt(sum residuals squared) / sqrt(sum target distances squared)",
}
V15_SCORE_PROTOCOL = {
    "standardization_sd": "population",
    "representative": "median",
    "display_base": 50.0,
    "display_scale": 10.0,
    "spread_metric": "performance",
    "spread_stat": "population_sd",
    "spread_scale": 10.0,
}
V15_SELECTED_BENCHMARKS = {
    "Agents' Last Exam",
    "GDPval-AA v2",
    "DeepSWE v1.1",
    "Terminal-Bench 2.1",
    "BrowseComp",
    "OSWorld 2.0",
    "AutomationBench",
}
V15_EXCLUDED_BENCHMARKS = {
    "Artificial Analysis Intelligence Index v4.1",
    "Artificial Analysis Coding Agent Index v1.1",
}
V15_MODEL_ORDER = ["GPT-5.5", "GPT-5.6 Luna", "GPT-5.6 Terra", "GPT-5.6 Sol"]
V15_EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max"]
V15_PRICE_SOURCE = "https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/"
V15_SOL_SOURCE = "https://openai.com/index/gpt-5-6/"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_display_transform(value) -> bool:
    if value == "z":
        return True
    if isinstance(value, dict):
        return set(value) >= {"base", "scale"} and all(isinstance(value[key], (int, float)) and math.isfinite(float(value[key])) for key in ("base", "scale")) and float(value["scale"]) > 0
    if not isinstance(value, str):
        return False
    match = re.fullmatch(r"\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*\+\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*[×*]?\s*z\s*", value)
    return bool(match and float(match.group(1)) > 0)


def display_parameters(value):
    if value == "z":
        return 0.0, 1.0
    if isinstance(value, dict):
        return float(value["base"]), float(value["scale"])
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*\+\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*[×*]?\s*z\s*", value)
    if not match:
        raise ValueError("unsupported display transform")
    return float(match.group(1)), float(match.group(2))


def adjustment_applies(rule, point, benchmark, metric):
    if rule.get("metric") != metric:
        return False
    if rule.get("benchmark") not in (None, "*", benchmark):
        return False
    if rule.get("model") not in (None, "*", point.get("model")):
        return False
    if rule.get("effort") not in (None, "*", point.get("effort")):
        return False
    rule_mode = rule.get("mode")
    if rule_mode not in (None, "*"):
        point_mode = point.get("mode") or point.get("run_mode") or "normal"
        if rule_mode != point_mode:
            return False
    return True


def adjusted_value(point, benchmark, metric, spec, rules):
    raw = float(point["raw"][benchmark][spec["field"]])
    adjusted = raw
    for rule in rules:
        if adjustment_applies(rule, point, benchmark, metric):
            adjusted *= float(rule["multiplier"])
    return raw, adjusted


def independent_representative_check(source, config, rows):
    """Recompute representative display values separately from compute_tradeoff_scores.py."""
    points = list(source.get("points", []))
    selected = list(config["selected_benchmarks"])
    metrics = config["metrics"]
    rules = list(config.get("adjustments", []))
    sd_kind = config["standardization"].get("sd", "population")
    representative_kind = config.get("representative", "median")
    base, scale = display_parameters(config.get("display_transform", "50 + 10z"))
    z_values = {point["id"]: {metric: [] for metric in metrics} for point in points}
    for benchmark in selected:
        for metric, spec in metrics.items():
            directional = []
            for point in points:
                _, adjusted = adjusted_value(point, benchmark, metric, spec, rules)
                directional.append(adjusted * float(spec["direction"]))
            mean = sum(directional) / len(directional)
            denominator = len(directional) if sd_kind == "population" else len(directional) - 1
            sd = math.sqrt(sum((value - mean) ** 2 for value in directional) / denominator)
            for point, value in zip(points, directional):
                z_values[point["id"]][metric].append((value - mean) / sd)
    errors = []
    for point in points:
        row = rows.get(point["id"])
        if row is None:
            continue
        for metric in metrics:
            values = z_values[point["id"]][metric]
            representative = float(median(values)) if representative_kind == "median" else sum(values) / len(values)
            expected_score = base + scale * representative
            score_key = f"{metric}_deviation_score" if f"{metric}_deviation_score" in row else f"{metric}_score"
            try:
                if not math.isclose(float(row[score_key]), expected_score, rel_tol=1e-9, abs_tol=1e-9):
                    errors.append(f"{point['id']} {metric} representative mismatch")
                z_key = f"{metric}_z_{representative_kind}"
                if z_key in row and not math.isclose(float(row[z_key]), representative, rel_tol=1e-9, abs_tol=1e-9):
                    errors.append(f"{point['id']} {metric} z representative mismatch")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{point['id']} {metric} representative is not numeric")
        if "performance" in metrics and "performance_sd_points" in row:
            performance_values = z_values[point["id"]]["performance"]
            performance_mean = sum(performance_values) / len(performance_values)
            spread_scale = float(config.get("variability", {}).get("display_scale", 10.0))
            expected_spread = spread_scale * math.sqrt(sum((value - performance_mean) ** 2 for value in performance_values) / len(performance_values))
            try:
                if not math.isclose(float(row["performance_sd_points"]), expected_spread, rel_tol=1e-9, abs_tol=1e-9):
                    errors.append(f"{point['id']} performance spread mismatch")
            except (TypeError, ValueError):
                errors.append(f"{point['id']} performance spread is not numeric")
    return errors


def pareto_ids_from_rows(rows, axes):
    """Return the non-dominated ids using internal representative columns."""
    values = {}
    for candidate_id, row in rows.items():
        try:
            values[candidate_id] = [float(row[axis]) for axis in axes]
        except (KeyError, TypeError, ValueError):
            continue
    pareto = []
    for candidate_id, candidate_values in values.items():
        dominated = False
        for other_id, other_values in values.items():
            if other_id == candidate_id:
                continue
            if all(other_values[index] >= candidate_values[index] for index in range(len(axes))) and any(other_values[index] > candidate_values[index] for index in range(len(axes))):
                dominated = True
                break
        if not dominated:
            pareto.append(candidate_id)
    return set(pareto)


def v15_expected_candidate_ids():
    return {
        f"{model}|{effort}"
        for model in V15_MODEL_ORDER
        for effort in V15_EFFORT_ORDER
        if not (model == "GPT-5.5" and effort == "max")
    }


def valid_provenance_url(value):
    raw = str(value)
    try:
        parsed = urlparse(raw)
        hostname = (parsed.hostname or "").rstrip(".").lower()
    except ValueError:
        return False
    reserved_suffixes = (".invalid", ".test", ".localhost", ".example")
    reserved_hosts = {"example.com", "example.org", "example.net", "invalid", "localhost", "test"}
    return (
        parsed.scheme == "https"
        and bool(hostname)
        and "." in hostname
        and hostname not in reserved_hosts
        and not hostname.endswith(reserved_suffixes)
        and not hostname.endswith((".example.com", ".example.org", ".example.net"))
        and " " not in raw
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--representatives", type=Path, required=True, help="generated representatives CSV; release validation independently recomputes it")
    args = parser.parse_args()
    source = read_json(args.input)
    config = read_json(args.config)
    errors: list[str] = []
    required = ["analysis_mode", "selected_benchmarks", "excluded_benchmarks", "model_order", "effort_order", "metrics", "standardization", "representative", "display_transform", "pareto", "mds"]
    for key in required:
        if key not in config:
            errors.append(f"missing method key {key}")
    selected = set(config.get("selected_benchmarks", []))
    excluded = set(config.get("excluded_benchmarks", []))
    if selected & excluded:
        errors.append("selected and excluded benchmarks overlap")
    points = source.get("points", [])
    ids = [point.get("id") for point in points]
    if len(ids) != len(set(ids)):
        errors.append("candidate ids are not unique")
    expected_count = config.get("candidate_count")
    if expected_count is not None and len(points) != int(expected_count):
        errors.append(f"candidate count is {len(points)}, expected {expected_count}")
    for key, expected in (("selected_benchmarks", selected), ("excluded_benchmarks", excluded)):
        if key not in source:
            errors.append(f"source is missing required {key}")
        elif set(source.get(key, [])) != expected:
            errors.append(f"source and config {key} do not match")

    analysis_mode = config.get("analysis_mode")
    metric_names = set(config.get("metrics", {}))
    if analysis_mode in {"three_axis_v15", "three_axis_generic"} and metric_names != {"performance", "cost", "latency"}:
        errors.append(f"{analysis_mode} requires exactly performance, cost, and latency metrics")
    if analysis_mode == "reduced_2d" and len(metric_names) != 2:
        errors.append("reduced_2d requires exactly two metrics")
    if analysis_mode not in {"three_axis_v15", "three_axis_generic", "reduced_2d"}:
        errors.append(f"unknown analysis_mode: {analysis_mode!r}")
    if analysis_mode == "three_axis_v15":
        if selected != V15_SELECTED_BENCHMARKS or excluded != V15_EXCLUDED_BENCHMARKS:
            errors.append("three_axis_v15 requires the fixed seven selected and two excluded benchmark sets")
        if config.get("model_order") != V15_MODEL_ORDER:
            errors.append("three_axis_v15 model_order does not match the v15 candidate set")
        if config.get("effort_order") != V15_EFFORT_ORDER:
            errors.append("three_axis_v15 effort_order does not match the v15 candidate set")
        if config.get("missing_value_policy") != "error":
            errors.append("three_axis_v15 requires missing_value_policy=error")
        expected_ids = v15_expected_candidate_ids()
        if set(ids) != expected_ids:
            errors.append("three_axis_v15 candidate ids do not match the fixed model×effort set")
        for point in points:
            if point.get("id") != f"{point.get('model')}|{point.get('effort')}":
                errors.append(f"candidate {point.get('id')!r} does not encode model|effort")
            if point.get("model") not in V15_MODEL_ORDER or point.get("effort") not in V15_EFFORT_ORDER:
                errors.append(f"candidate {point.get('id')!r} has a model or effort outside v15 order")
    pareto = config.get("pareto", {})
    pareto_axes = set(pareto.get("axes", []))
    if analysis_mode in {"three_axis_v15", "three_axis_generic"}:
        if pareto_axes != {"performance", "cost", "latency"} or pareto.get("authoritative") is not True:
            errors.append(f"{analysis_mode} requires an authoritative performance/cost/latency Pareto contract")
        expected_directions = {"performance": 1, "cost": -1, "latency": -1}
        for metric, direction in expected_directions.items():
            if analysis_mode == "three_axis_v15" and config.get("metrics", {}).get(metric, {}).get("direction") != direction:
                errors.append(f"v15 direction for {metric} must be {direction}")
    elif analysis_mode == "reduced_2d" and pareto.get("authoritative") is True:
        errors.append("reduced_2d must not claim an authoritative three-axis Pareto set")
    if analysis_mode == "reduced_2d":
        reduced_mds = config.get("mds", {})
        if reduced_mds.get("fit_ids") or reduced_mds.get("excluded_ids") or reduced_mds.get("projection_only_ids"):
            errors.append("reduced_2d must not configure a v15 MDS fit")

    standardization = config.get("standardization", {})
    if standardization.get("scope") != "within_benchmark":
        errors.append("standardization.scope must be within_benchmark")
    if standardization.get("sd") not in {"population", "sample"}:
        errors.append("standardization.sd must be population or sample")
    if not isinstance(standardization.get("log_transform", False), bool):
        errors.append("standardization.log_transform must be boolean")
    if standardization.get("log_transform", False):
        errors.append("log_transform is not supported by the bundled calculator")
    if config.get("representative", "median") not in {"median", "mean"}:
        errors.append("representative must be median or mean")
    if not valid_display_transform(config.get("display_transform", "50 + 10z")):
        errors.append("display_transform is not a supported derived-score expression")
    if analysis_mode == "three_axis_v15":
        if standardization.get("sd") != V15_SCORE_PROTOCOL["standardization_sd"]:
            errors.append("three_axis_v15 requires population SD")
        if config.get("representative") != V15_SCORE_PROTOCOL["representative"]:
            errors.append("three_axis_v15 requires median representatives")
        try:
            display_base, display_scale = display_parameters(config["display_transform"])
            if display_base != V15_SCORE_PROTOCOL["display_base"] or display_scale != V15_SCORE_PROTOCOL["display_scale"]:
                errors.append("three_axis_v15 requires display transform 50 + 10z")
        except (KeyError, TypeError, ValueError):
            errors.append("three_axis_v15 display transform is invalid")
        variability = config.get("variability", {})
        if variability.get("metric") != V15_SCORE_PROTOCOL["spread_metric"] or variability.get("stat") != V15_SCORE_PROTOCOL["spread_stat"]:
            errors.append("three_axis_v15 requires population performance task spread")
        try:
            if float(variability.get("display_scale")) != V15_SCORE_PROTOCOL["spread_scale"]:
                errors.append("three_axis_v15 requires task-spread display scale 10")
        except (TypeError, ValueError):
            errors.append("three_axis_v15 task-spread display scale is invalid")
    for metric, spec in config.get("metrics", {}).items():
        if spec.get("direction") not in (-1, 1):
            errors.append(f"metric {metric} direction must be 1 or -1")
        if not spec.get("field"):
            errors.append(f"metric {metric} lacks a raw field")
    for index, rule in enumerate(config.get("adjustments", [])):
        try:
            multiplier = float(rule.get("multiplier"))
        except (TypeError, ValueError):
            multiplier = float("nan")
        if not math.isfinite(multiplier) or multiplier <= 0:
            errors.append(f"adjustment[{index}] multiplier must be finite and positive")
        source_url = rule.get("source_url")
        effective_date = rule.get("effective_date")
        try:
            date.fromisoformat(str(effective_date))
        except (TypeError, ValueError):
            effective_date = None
        if not valid_provenance_url(source_url) or not effective_date or rule.get("provenance_status") not in {"reviewed", "verified"}:
            errors.append(f"adjustment[{index}] needs source_url and effective_date")
    for index, rule in enumerate(config.get("non_applied_interventions", [])):
        if not valid_provenance_url(rule.get("source_url")) or not rule.get("reason") or rule.get("provenance_status") not in {"reviewed", "verified"}:
            errors.append(f"non_applied_interventions[{index}] needs source_url and reason")
    if analysis_mode == "three_axis_v15":
        expected_adjustments = [
            ("GPT-5.6 Luna", "cost", 0.20, "normal", "2026-07-30", V15_PRICE_SOURCE),
            ("GPT-5.6 Terra", "cost", 0.80, "normal", "2026-07-30", V15_PRICE_SOURCE),
        ]
        actual_adjustments = []
        for rule in config.get("adjustments", []):
            try:
                rule_multiplier = float(rule.get("multiplier"))
            except (TypeError, ValueError):
                rule_multiplier = float("nan")
            actual_adjustments.append((
                rule.get("model"), rule.get("metric"), rule_multiplier,
                rule.get("mode"), rule.get("effective_date"), rule.get("source_url"),
            ))
            if rule.get("benchmark") is not None or rule.get("effort") is not None:
                errors.append("three_axis_v15 cost adjustments must apply to the whole normal-mode model")
        if len(actual_adjustments) != len(expected_adjustments) or any(
            not any(
                actual[:2] == expected[:2] and math.isclose(actual[2], expected[2], rel_tol=0.0, abs_tol=0.0)
                and actual[3:] == expected[3:]
                for expected in expected_adjustments
            )
            for actual in actual_adjustments
        ):
            errors.append("three_axis_v15 adjustments must be the reviewed Luna 0.20 and Terra 0.80 normal-mode cost reductions")
        interventions = config.get("non_applied_interventions", [])
        if len(interventions) != 1:
            errors.append("three_axis_v15 requires one non-applied Sol Fast-mode latency intervention record")
        else:
            intervention = interventions[0]
            if (
                intervention.get("model") != "GPT-5.6 Sol"
                or intervention.get("metric") != "latency"
                or intervention.get("mode") != "fast"
                or intervention.get("applied") is not False
                or intervention.get("source_url") != V15_SOL_SOURCE
                or "fast" not in str(intervention.get("reason", "")).lower()
                or "normal" not in str(intervention.get("reason", "")).lower()
                or "not applied" not in str(intervention.get("reason", "")).lower()
                or "unchanged" not in str(intervention.get("reason", "")).lower()
            ):
                errors.append("three_axis_v15 must record applied=false and that Sol Fast-only latency was not applied and remains unchanged in normal mode")

    missing_cells = []
    nonfinite_cells = []
    for point in points:
        raw = point.get("raw", {})
        for benchmark in selected:
            record = raw.get(benchmark)
            if not isinstance(record, dict):
                missing_cells.append(f"{point.get('id')} / {benchmark}")
                continue
            for metric, spec in config.get("metrics", {}).items():
                field = spec.get("field")
                if field not in record:
                    missing_cells.append(f"{point.get('id')} / {benchmark} / {metric}")
                    continue
                try:
                    value = float(record[field])
                except (TypeError, ValueError):
                    nonfinite_cells.append(f"{point.get('id')} / {benchmark} / {metric}")
                    continue
                if not math.isfinite(value):
                    nonfinite_cells.append(f"{point.get('id')} / {benchmark} / {metric}")
    if missing_cells:
        errors.append(f"missing raw cells: {len(missing_cells)} (no silent imputation is allowed)")
    if nonfinite_cells:
        errors.append(f"non-finite raw cells: {len(nonfinite_cells)}")
    mds = config.get("mds", {})
    fit = set(mds.get("fit_ids", []))
    mds_excluded = set(mds.get("excluded_ids", []))
    projection = set(mds.get("projection_only_ids", []))
    if fit & mds_excluded or fit & projection or mds_excluded & projection:
        errors.append("MDS fit, excluded, and projection-only sets overlap")
    unknown_mds = (fit | mds_excluded | projection) - set(ids)
    if unknown_mds:
        errors.append(f"MDS references unknown candidates: {sorted(unknown_mds)}")
    if mds.get("fit_count") is not None and int(mds["fit_count"]) != len(fit):
        errors.append("mds.fit_count does not match mds.fit_ids")
    if mds.get("projection_only_count") is not None and int(mds["projection_only_count"]) != len(projection):
        errors.append("mds.projection_only_count does not match mds.projection_only_ids")
    if mds.get("edge_source") not in (None, "grid_adjacency"):
        errors.append("MDS edge_source must be grid_adjacency for this workflow")
    if analysis_mode == "three_axis_v15" and mds.get("distance_method") not in (None, "metric_mds"):
        errors.append("three_axis_v15 requires metric_mds")
    if analysis_mode == "three_axis_v15":
        missing_protocol = [key for key in V15_MDS_PROTOCOL if key not in mds]
        if missing_protocol:
            errors.append(f"three_axis_v15 MDS config is missing protocol keys: {missing_protocol}")
        representative_kind = config.get("representative", "median")
        expected_axes = [f"{metric}_z_{representative_kind}" for metric in ("performance", "cost", "latency")]
        if mds.get("distance_axes") != expected_axes:
            errors.append("three_axis_v15 MDS distance_axes must be the internal representative z columns")
        for key, expected in V15_MDS_PROTOCOL.items():
            if mds.get(key) != expected:
                errors.append(f"three_axis_v15 MDS {key} must use the fixed v15 protocol")
        if mds.get("distance_method") != "metric_mds":
            errors.append("three_axis_v15 requires distance_method=metric_mds")
        if mds.get("edge_source") != "grid_adjacency":
            errors.append("three_axis_v15 requires edge_source=grid_adjacency")
    if args.representatives:
        with args.representatives.open(encoding="utf-8", newline="") as handle:
            rows_list = list(csv.DictReader(handle))
        rows = {row.get("id"): row for row in rows_list}
        if set(rows) != set(ids):
            errors.append("representative IDs do not match input candidates")
        for metric in config.get("metrics", {}):
            expected_fields = {f"{metric}_deviation_score", f"{metric}_score"}
            if rows_list and not expected_fields & set(rows_list[0]):
                errors.append(f"representatives lack a display field for {metric}")
        if analysis_mode == "three_axis_v15" and rows:
            if len(points) != 19 or len(selected) != 7:
                errors.append("three_axis_v15 requires 19 candidates and seven selected benchmarks")
            representative_kind = config.get("representative", "median")
            internal_axes = [f"{metric}_z_{representative_kind}" for metric in ("performance", "cost", "latency")]
            pareto_ids = pareto_ids_from_rows(rows, internal_axes)
            anchor_ids = mds.get("anchor_ids")
            excluded_model_names = mds.get("excluded_model_names")
            if not isinstance(anchor_ids, list) or not anchor_ids:
                errors.append("three_axis_v15 MDS must declare non-empty anchor_ids")
                anchor_ids = []
            if not isinstance(excluded_model_names, list) or not excluded_model_names:
                errors.append("three_axis_v15 MDS must declare excluded_model_names")
                excluded_model_names = []
            expected_pareto_count = mds.get("expected_pareto_count")
            if expected_pareto_count != 14 or len(pareto_ids) != 14:
                errors.append("three_axis_v15 requires an independently recomputed 14-point Pareto set")
            expected_fit = pareto_ids | set(anchor_ids)
            expected_excluded = {point.get("id") for point in points if point.get("model") in set(excluded_model_names)}
            if set(anchor_ids) & pareto_ids:
                errors.append("three_axis_v15 MDS anchors must be distinct from the Pareto set")
            if set(mds.get("fit_ids", [])) != expected_fit:
                errors.append("three_axis_v15 MDS fit_ids must equal Pareto ids union anchor_ids")
            if set(mds.get("excluded_ids", [])) != expected_excluded or set(mds.get("excluded_ids", [])) != set(ids) - expected_fit:
                errors.append("three_axis_v15 MDS excluded_ids must be the declared excluded model set and complement the fit")
            if mds.get("projection_only_ids", []) != []:
                errors.append("three_axis_v15 MDS projection_only_ids must be empty")
            if mds.get("fit_count") != len(expected_fit) or len(expected_fit) != 15:
                errors.append("three_axis_v15 MDS fit must contain 15 candidates")
        errors.extend(independent_representative_check(source, config, rows))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: tradeoff contract validated for {len(ids)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
