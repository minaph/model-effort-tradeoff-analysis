#!/usr/bin/env python3
"""Compute v15-style directional benchmark z-scores and representatives."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from statistics import median
from typing import Any


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

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def adjustment_applies(rule: dict[str, Any], point: dict[str, Any], benchmark: str, metric: str) -> bool:
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


def adjusted_value(point: dict[str, Any], benchmark: str, metric: str, spec: dict[str, Any], rules: list[dict[str, Any]]) -> tuple[float, float]:
    record = point["raw"][benchmark]
    raw = float(record[spec["field"]])
    adjusted = raw
    for rule in rules:
        if adjustment_applies(rule, point, benchmark, metric):
            multiplier = float(rule["multiplier"])
            if not math.isfinite(multiplier) or multiplier <= 0:
                raise ValueError(f"invalid multiplier for {metric}: {multiplier}")
            adjusted *= multiplier
    return raw, adjusted


def population_mean_sd(values: list[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("cannot standardize an empty set")
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
    if sd == 0:
        raise ValueError("population SD is zero; z-score is undefined")
    return mean, sd


def mean_sd(values: list[float], kind: str) -> tuple[float, float]:
    if kind == "population":
        return population_mean_sd(values)
    if kind != "sample":
        raise ValueError("standardization.sd must be 'population' or 'sample'")
    if len(values) < 2:
        raise ValueError("sample SD requires at least two candidates")
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
    if sd == 0:
        raise ValueError("sample SD is zero; z-score is undefined")
    return mean, sd


def representative_value(values: list[float], kind: str) -> float:
    if kind == "median":
        return float(median(values))
    if kind == "mean":
        return sum(values) / len(values)
    raise ValueError("representative must be 'median' or 'mean'")


def display_parameters(value: Any) -> tuple[float, float]:
    if isinstance(value, dict):
        base = float(value["base"])
        scale = float(value["scale"])
    elif value == "z":
        base, scale = 0.0, 1.0
    elif isinstance(value, str):
        match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*\+\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*[×*]?\s*z\s*", value)
        if not match:
            raise ValueError("display_transform must be 'z', '<base> + <scale>z', or {base, scale}; raw is not a derived score")
        base, scale = float(match.group(1)), float(match.group(2))
    else:
        raise ValueError("invalid display_transform")
    if not math.isfinite(base) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("display_transform base must be finite and scale must be finite and positive")
    return base, scale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source = read_json(args.input)
    config = read_json(args.config)
    selected = list(config["selected_benchmarks"])
    metrics = config["metrics"]
    standardization = config.get("standardization", {})
    if standardization.get("scope") != "within_benchmark":
        raise ValueError("standardization.scope must be 'within_benchmark'")
    if standardization.get("log_transform", False):
        raise ValueError("log transform is not supported by this deterministic calculator; use a separately reviewed protocol")
    sd_kind = standardization.get("sd", "population")
    representative_kind = config.get("representative", "median")
    display_base, display_scale = display_parameters(config.get("display_transform", "50 + 10z"))
    if "analysis_mode" not in config:
        raise ValueError("missing required analysis_mode")
    analysis_mode = config["analysis_mode"]
    if analysis_mode not in {"three_axis_v15", "three_axis_generic", "reduced_2d"}:
        raise ValueError(f"unknown analysis_mode: {analysis_mode!r}")
    if analysis_mode == "three_axis_v15":
        if sd_kind != "population":
            raise ValueError("three_axis_v15 requires population SD")
        if representative_kind != "median":
            raise ValueError("three_axis_v15 requires median representatives")
        if (display_base, display_scale) != (50.0, 10.0):
            raise ValueError("three_axis_v15 requires display transform 50 + 10z")
        if set(metrics) != {"performance", "cost", "latency"}:
            raise ValueError("three_axis_v15 requires performance, cost, and latency metrics")
        expected_directions = {"performance": 1, "cost": -1, "latency": -1}
        for metric, direction in expected_directions.items():
            if metrics[metric].get("direction") != direction:
                raise ValueError(f"three_axis_v15 direction for {metric} must be {direction}")
        variability = config.get("variability", {})
        if variability.get("metric") != "performance" or variability.get("stat") != "population_sd" or float(variability.get("display_scale")) != 10.0:
            raise ValueError("three_axis_v15 requires population performance task spread scaled by 10")
    elif analysis_mode == "three_axis_generic" and set(metrics) != {"performance", "cost", "latency"}:
        raise ValueError("three_axis_generic requires exactly performance, cost, and latency metrics")
    points = list(source["points"])
    ids = [point["id"] for point in points]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate ids must be unique")
    excluded = set(config.get("excluded_benchmarks", []))
    if analysis_mode == "three_axis_v15":
        if set(selected) != V15_SELECTED_BENCHMARKS or excluded != V15_EXCLUDED_BENCHMARKS:
            raise ValueError("three_axis_v15 requires the fixed seven selected and two excluded benchmark sets")
        if config.get("model_order") != V15_MODEL_ORDER or config.get("effort_order") != V15_EFFORT_ORDER:
            raise ValueError("three_axis_v15 requires the fixed model and effort order")
        if config.get("missing_value_policy") != "error":
            raise ValueError("three_axis_v15 requires missing_value_policy=error")
        expected_ids = {
            f"{model}|{effort}"
            for model in V15_MODEL_ORDER
            for effort in V15_EFFORT_ORDER
            if not (model == "GPT-5.5" and effort == "max")
        }
        if set(ids) != expected_ids:
            raise ValueError("three_axis_v15 requires the fixed model×effort candidate set")
        for point in points:
            if point.get("id") != f"{point.get('model')}|{point.get('effort')}":
                raise ValueError(f"candidate {point.get('id')!r} does not encode model|effort")
        expected_adjustments = {
            ("GPT-5.6 Luna", "cost", 0.20, "normal", "2026-07-30", V15_PRICE_SOURCE),
            ("GPT-5.6 Terra", "cost", 0.80, "normal", "2026-07-30", V15_PRICE_SOURCE),
        }
        actual_adjustments = set()
        for rule in config.get("adjustments", []):
            try:
                multiplier = float(rule.get("multiplier"))
            except (TypeError, ValueError):
                raise ValueError("v15 adjustment multiplier must be numeric")
            if rule.get("benchmark") is not None or rule.get("effort") is not None:
                raise ValueError("v15 cost adjustments must apply to the whole normal-mode model")
            actual_adjustments.add((rule.get("model"), rule.get("metric"), multiplier, rule.get("mode"), rule.get("effective_date"), rule.get("source_url")))
        if len(config.get("adjustments", [])) != len(expected_adjustments) or actual_adjustments != expected_adjustments:
            raise ValueError("three_axis_v15 requires the reviewed Luna 0.20 and Terra 0.80 normal-mode cost reductions")
        interventions = config.get("non_applied_interventions", [])
        if len(interventions) != 1:
            raise ValueError("three_axis_v15 requires one non-applied Sol Fast-mode latency intervention record")
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
            raise ValueError("three_axis_v15 must record applied=false and that Sol Fast-only latency was not applied and remains unchanged in normal mode")
    if set(selected) & excluded:
        raise ValueError("selected and excluded benchmarks overlap")
    for key in ("selected_benchmarks", "excluded_benchmarks"):
        if key not in source:
            raise ValueError(f"source is missing required {key}")
        if set(source.get(key, [])) != (set(selected) if key == "selected_benchmarks" else excluded):
            raise ValueError(f"source and config {key} do not match")
    expected_count = config.get("candidate_count")
    if expected_count is not None and len(points) != int(expected_count):
        raise ValueError(f"expected {expected_count} candidates, found {len(points)}")
    rules = list(config.get("adjustments", []))

    stats: dict[str, dict[str, dict[str, float | int | str]]] = {}
    values: dict[str, dict[str, dict[str, dict[str, float | str]]]] = {point["id"]: {} for point in points}
    for benchmark in selected:
        stats[benchmark] = {}
        for metric, spec in metrics.items():
            directional: list[float] = []
            records: list[tuple[str, float, float]] = []
            for point in points:
                if benchmark not in point.get("raw", {}):
                    raise ValueError(f"missing benchmark {benchmark!r} for {point['id']}")
                raw, adjusted = adjusted_value(point, benchmark, metric, spec, rules)
                if not math.isfinite(raw) or not math.isfinite(adjusted):
                    raise ValueError(f"non-finite value for {point['id']} / {benchmark} / {metric}")
                direction = float(spec.get("direction", 1))
                if direction not in (-1.0, 1.0):
                    raise ValueError(f"direction must be 1 or -1 for {metric}")
                value = adjusted * direction
                directional.append(value)
                records.append((point["id"], raw, adjusted))
            mean, sd = mean_sd(directional, sd_kind)
            stats[benchmark][metric] = {
                "mean": mean,
                "sd": sd,
                "sd_kind": sd_kind,
                "population_sd": sd if sd_kind == "population" else None,
                "direction": int(spec.get("direction", 1)),
                "field": spec["field"],
            }
            for (point_id, raw, adjusted), value in zip(records, directional):
                values[point_id].setdefault(benchmark, {})[metric] = {
                    "raw": raw,
                    "adjusted": adjusted,
                    "directional": value,
                    "z": (value - mean) / sd,
                }

    representatives: list[dict[str, Any]] = []
    for point in points:
        by_benchmark = values[point["id"]]
        row: dict[str, Any] = {"id": point["id"], "model": point["model"], "effort": point["effort"]}
        for metric in metrics:
            z_values = [float(by_benchmark[benchmark][metric]["z"]) for benchmark in selected]
            row[f"{metric}_z_{representative_kind}"] = representative_value(z_values, representative_kind)
            row[f"{metric}_deviation_score"] = display_base + display_scale * row[f"{metric}_z_{representative_kind}"]
        if "performance" in metrics:
            performance_z = [float(by_benchmark[benchmark]["performance"]["z"]) for benchmark in selected]
            mean = sum(performance_z) / len(performance_z)
            variability = config.get("variability", {})
            if variability.get("metric", "performance") != "performance":
                raise ValueError("this calculator defines task spread for the performance metric")
            if variability.get("stat", "population_sd") != "population_sd":
                raise ValueError("task spread must use population_sd in this calculator")
            spread_scale = float(variability.get("display_scale", 10.0))
            row["performance_sd_points"] = spread_scale * math.sqrt(sum((v - mean) ** 2 for v in performance_z) / len(performance_z))
        else:
            row["performance_sd_points"] = None
        representatives.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    standardized = {
        "version": config.get("version", "unversioned"),
        "selected_benchmarks": selected,
        "excluded_benchmarks": sorted(excluded),
        "population_statistics": stats,
        "points": [{"id": point["id"], "model": point["model"], "effort": point["effort"], "benchmarks": values[point["id"]]} for point in points],
    }
    (args.output_dir / "standardized.json").write_text(json.dumps(standardized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = ["id", "model", "effort"]
    fieldnames += [f"{metric}_z_{representative_kind}" for metric in metrics]
    fieldnames += [f"{metric}_deviation_score" for metric in metrics]
    fieldnames += ["performance_sd_points"]
    with (args.output_dir / "representatives.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(representatives)
    (args.output_dir / "summary.json").write_text(json.dumps({"candidate_count": len(points), "benchmark_count": len(selected), "representatives": representatives}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_count": len(points), "benchmark_count": len(selected), "output_dir": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
