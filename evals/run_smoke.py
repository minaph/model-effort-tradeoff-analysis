#!/usr/bin/env python3
"""Run an executable transfer fixture and negative-contract smoke test."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCRIPTS = ROOT / "scripts"


def run(*args: str, expect: int = 0):
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode != expect:
        raise RuntimeError(f"unexpected exit {result.returncode} for {' '.join(args)}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="model-effort-eval-") as temp:
        temp_path = Path(temp)
        output = temp_path / "scores"
        input_path = FIXTURES / "transfer_input.json"
        config_path = FIXTURES / "transfer_config.json"
        reps = output / "representatives.csv"
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(config_path), "--output-dir", str(output))
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(config_path), "--representatives", str(reps))
        built_grid = temp_path / "built-grid.json"
        run(sys.executable, str(SCRIPTS / "build_grid_edges.py"), "--input", str(input_path), "--config", str(config_path), "--output", str(built_grid))
        run(sys.executable, str(SCRIPTS / "validate_grid_edges.py"), "--input", str(input_path), "--edges", str(built_grid), "--config", str(config_path))
        mds_path = output / "mds.json"
        run(sys.executable, str(SCRIPTS / "compute_mds.py"), "--representatives", str(reps), "--config", str(config_path), "--output", str(mds_path))
        run(sys.executable, str(SCRIPTS / "validate_mds_scope.py"), "--input", str(input_path), "--config", str(config_path), "--mds", str(mds_path), "--representatives", str(reps))
        run(sys.executable, str(SCRIPTS / "compute_mds.py"), "--representatives", str(reps), "--config", str(config_path), "--axes", "performance_deviation_score", "cost_deviation_score", "latency_deviation_score", "--output", str(temp_path / "wrong-space-mds.json"), expect=1)
        built_mds = temp_path / "built-mds.json"
        run(sys.executable, str(SCRIPTS / "build_mds_edges.py"), "--grid-edges", str(built_grid), "--config", str(config_path), "--output", str(built_mds))
        run(sys.executable, str(SCRIPTS / "validate_grid_edges.py"), "--input", str(input_path), "--edges", str(built_grid), "--mds-edges", str(built_mds), "--config", str(config_path))

        rows = list(csv.DictReader(reps.open(encoding="utf-8", newline="")))
        scores = {row["id"]: tuple(float(row[field]) for field in ("performance_deviation_score", "cost_deviation_score", "latency_deviation_score")) for row in rows}
        pareto = []
        for candidate, values in scores.items():
            dominated = any(other != candidate and all(scores[other][i] >= values[i] for i in range(3)) and any(scores[other][i] > values[i] for i in range(3)) for other in scores)
            if not dominated:
                pareto.append(candidate)
        pareto_path = temp_path / "pareto.json"
        pareto_path.write_text(json.dumps({"pareto_ids": pareto}) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_pareto.py"), "--representatives", str(reps), "--pareto", str(pareto_path))

        # Benchmark list equality must preserve multiplicity: a repeated name
        # would otherwise change its weight in the per-benchmark median.
        base_input = json.loads(input_path.read_text(encoding="utf-8"))
        base_config = json.loads(config_path.read_text(encoding="utf-8"))
        for duplicate_side in ("input", "config", "both"):
            bad_input = json.loads(json.dumps(base_input))
            bad_config = json.loads(json.dumps(base_config))
            if duplicate_side in ("input", "both"):
                bad_input["selected_benchmarks"].append(bad_input["selected_benchmarks"][0])
            if duplicate_side in ("config", "both"):
                bad_config["selected_benchmarks"].append(bad_config["selected_benchmarks"][0])
            bad_input_path = temp_path / f"duplicate-{duplicate_side}-input.json"
            bad_config_path = temp_path / f"duplicate-{duplicate_side}-config.json"
            bad_input_path.write_text(json.dumps(bad_input) + "\n", encoding="utf-8")
            bad_config_path.write_text(json.dumps(bad_config) + "\n", encoding="utf-8")
            run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(bad_input_path), "--config", str(bad_config_path), "--output-dir", str(temp_path / f"duplicate-{duplicate_side}-scores"), expect=1)
            run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(bad_input_path), "--config", str(bad_config_path), "--representatives", str(reps), expect=1)

        # Excluded benchmark lists are checked too, despite not contributing
        # to the score calculation.
        for duplicate_side in ("input", "config"):
            bad_input = json.loads(json.dumps(base_input))
            bad_config = json.loads(json.dumps(base_config))
            duplicate_names = ["Ignored benchmark", "Ignored benchmark"]
            if duplicate_side == "input":
                bad_input["excluded_benchmarks"] = duplicate_names
            else:
                bad_config["excluded_benchmarks"] = duplicate_names
            bad_input_path = temp_path / f"duplicate-excluded-{duplicate_side}-input.json"
            bad_config_path = temp_path / f"duplicate-excluded-{duplicate_side}-config.json"
            bad_input_path.write_text(json.dumps(bad_input) + "\n", encoding="utf-8")
            bad_config_path.write_text(json.dumps(bad_config) + "\n", encoding="utf-8")
            run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(bad_input_path), "--config", str(bad_config_path), "--output-dir", str(temp_path / f"duplicate-excluded-{duplicate_side}-scores"), expect=1)
            run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(bad_input_path), "--config", str(bad_config_path), "--representatives", str(reps), expect=1)

        # Each declared Pareto axis must reject NaN and either infinity.
        for axis in ("performance_deviation_score", "cost_deviation_score", "latency_deviation_score"):
            for invalid_value in ("NaN", "Infinity", "-Infinity"):
                bad_rows = [dict(row) for row in rows]
                bad_rows[0][axis] = invalid_value
                bad_reps = temp_path / f"nonfinite-{axis}-{invalid_value}.csv"
                with bad_reps.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=bad_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(bad_rows)
                run(sys.executable, str(SCRIPTS / "validate_pareto.py"), "--representatives", str(bad_reps), "--pareto", str(pareto_path), expect=1)

        v15_config_path = ROOT / "references" / "v15_config.example.json"
        v15_config = json.loads(v15_config_path.read_text(encoding="utf-8"))
        v15_ids = [
            f"{model}|{effort}"
            for model in v15_config["model_order"]
            for effort in v15_config["effort_order"]
            if not (model == "GPT-5.5" and effort == "max")
        ]
        v15_anchor = "GPT-5.6 Sol|max"
        v15_front = [candidate_id for candidate_id in v15_ids if candidate_id != v15_anchor and not candidate_id.startswith("GPT-5.5|")]
        v15_points = []
        for index, candidate_id in enumerate(v15_front, start=1):
            model, effort = candidate_id.split("|", 1)
            multiplier = {"GPT-5.6 Luna": 0.2, "GPT-5.6 Terra": 0.8}.get(model, 1.0)
            record = {"performance": float(index), "cost": (index + 1) / multiplier, "latency_min": 50.0}
            v15_points.append({"id": candidate_id, "model": model, "effort": effort, "raw": {benchmark: dict(record) for benchmark in v15_config["selected_benchmarks"]}})
        anchor_model, anchor_effort = v15_anchor.split("|", 1)
        anchor_record = {"performance": 7.5, "cost": 20.0, "latency_min": 100.0}
        v15_points.append({"id": v15_anchor, "model": anchor_model, "effort": anchor_effort, "raw": {benchmark: dict(anchor_record) for benchmark in v15_config["selected_benchmarks"]}})
        for candidate_id in v15_ids:
            if candidate_id.startswith("GPT-5.5|"):
                model, effort = candidate_id.split("|", 1)
                record = {"performance": -10.0, "cost": 100.0, "latency_min": 100.0}
                v15_points.append({"id": candidate_id, "model": model, "effort": effort, "raw": {benchmark: dict(record) for benchmark in v15_config["selected_benchmarks"]}})
        v15_input = {"selected_benchmarks": v15_config["selected_benchmarks"], "excluded_benchmarks": v15_config["excluded_benchmarks"], "points": v15_points}
        v15_input_path = temp_path / "v15-scope-input.json"
        v15_input_path.write_text(json.dumps(v15_input, ensure_ascii=False) + "\n", encoding="utf-8")
        v15_output = temp_path / "v15-scope-out"
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(v15_input_path), "--config", str(v15_config_path), "--output-dir", str(v15_output))
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(v15_input_path), "--config", str(v15_config_path), "--representatives", str(v15_output / "representatives.csv"))
        v15_mds = temp_path / "v15-scope-mds.json"
        run(sys.executable, str(SCRIPTS / "compute_mds.py"), "--representatives", str(v15_output / "representatives.csv"), "--config", str(v15_config_path), "--output", str(v15_mds))
        run(sys.executable, str(SCRIPTS / "validate_mds_scope.py"), "--input", str(v15_input_path), "--config", str(v15_config_path), "--mds", str(v15_mds), "--representatives", str(v15_output / "representatives.csv"))
        unknown_mds_mode_config = json.loads(v15_config_path.read_text(encoding="utf-8"))
        unknown_mds_mode_config["analysis_mode"] = "three_axis_unknown"
        unknown_mds_mode_path = temp_path / "v15-unknown-mds-mode.json"
        unknown_mds_mode_path.write_text(json.dumps(unknown_mds_mode_config, ensure_ascii=False) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_mds_scope.py"), "--input", str(v15_input_path), "--config", str(unknown_mds_mode_path), "--mds", str(v15_mds), "--representatives", str(v15_output / "representatives.csv"), expect=1)
        wrong_fit_config = json.loads(v15_config_path.read_text(encoding="utf-8"))
        wrong_fit_config["mds"]["fit_ids"] = [candidate_id for candidate_id in wrong_fit_config["mds"]["fit_ids"] if candidate_id != "GPT-5.6 Sol|low"] + ["GPT-5.5|low"]
        wrong_fit_config["mds"]["excluded_ids"] = [candidate_id for candidate_id in wrong_fit_config["mds"]["excluded_ids"] if candidate_id != "GPT-5.5|low"] + ["GPT-5.6 Sol|low"]
        wrong_fit_path = temp_path / "v15-wrong-fit.json"
        wrong_fit_path.write_text(json.dumps(wrong_fit_config, ensure_ascii=False) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(v15_input_path), "--config", str(wrong_fit_path), "--representatives", str(v15_output / "representatives.csv"), expect=1)
        wrong_projection_config = json.loads(v15_config_path.read_text(encoding="utf-8"))
        wrong_projection_config["mds"]["excluded_ids"] = [candidate_id for candidate_id in wrong_projection_config["mds"]["excluded_ids"] if candidate_id != "GPT-5.5|low"]
        wrong_projection_config["mds"]["projection_only_ids"] = ["GPT-5.5|low"]
        wrong_projection_path = temp_path / "v15-wrong-projection.json"
        wrong_projection_path.write_text(json.dumps(wrong_projection_config, ensure_ascii=False) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(v15_input_path), "--config", str(wrong_projection_path), "--representatives", str(v15_output / "representatives.csv"), expect=1)
        affirmative_sol_config = json.loads(v15_config_path.read_text(encoding="utf-8"))
        affirmative_sol_config["non_applied_interventions"][0]["reason"] = "Fast and normal mode latency adjustment was applied."
        affirmative_sol_path = temp_path / "v15-affirmative-sol-reason.json"
        affirmative_sol_path.write_text(json.dumps(affirmative_sol_config, ensure_ascii=False) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(v15_input_path), "--config", str(affirmative_sol_path), "--output-dir", str(temp_path / "v15-affirmative-sol-out"), expect=1)

        invalid = json.loads(config_path.read_text(encoding="utf-8"))
        invalid["display_transform"] = "raw"
        invalid_path = temp_path / "invalid.json"
        invalid_path.write_text(json.dumps(invalid) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(invalid_path), "--output-dir", str(temp_path / "invalid-out"), expect=1)

        v15_score_drift = json.loads(config_path.read_text(encoding="utf-8"))
        v15_score_drift["analysis_mode"] = "three_axis_v15"
        v15_score_drift["standardization"]["sd"] = "sample"
        v15_score_drift["representative"] = "mean"
        v15_score_drift["display_transform"] = {"base": 0, "scale": 1}
        v15_score_drift["variability"]["display_scale"] = 1
        v15_score_drift_path = temp_path / "v15-score-drift.json"
        v15_score_drift_path.write_text(json.dumps(v15_score_drift) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(v15_score_drift_path), "--output-dir", str(temp_path / "v15-score-drift-out"), expect=1)

        unknown_mode = json.loads(config_path.read_text(encoding="utf-8"))
        unknown_mode["analysis_mode"] = "three_axis_unknown"
        unknown_mode_path = temp_path / "unknown-mode.json"
        unknown_mode_path.write_text(json.dumps(unknown_mode) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(unknown_mode_path), "--output-dir", str(temp_path / "unknown-mode-out"), expect=1)
        missing_mode = json.loads(config_path.read_text(encoding="utf-8"))
        missing_mode.pop("analysis_mode")
        missing_mode_path = temp_path / "missing-mode.json"
        missing_mode_path.write_text(json.dumps(missing_mode) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(missing_mode_path), "--output-dir", str(temp_path / "missing-mode-out"), expect=1)
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(missing_mode_path), "--representatives", str(reps), expect=1)
        run(sys.executable, str(SCRIPTS / "compute_mds.py"), "--representatives", str(reps), "--config", str(missing_mode_path), "--output", str(temp_path / "missing-mode-mds.json"), expect=1)

        bad_generic_metrics = json.loads(config_path.read_text(encoding="utf-8"))
        bad_generic_metrics["metrics"].pop("latency")
        bad_generic_metrics["mds"]["distance_axes"] = ["performance_z_median", "cost_z_median"]
        bad_generic_metrics_path = temp_path / "bad-generic-metrics.json"
        bad_generic_metrics_path.write_text(json.dumps(bad_generic_metrics) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(bad_generic_metrics_path), "--output-dir", str(temp_path / "bad-generic-metrics-out"), expect=1)
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(bad_generic_metrics_path), "--representatives", str(reps), expect=1)

        invalid_direction = json.loads(config_path.read_text(encoding="utf-8"))
        invalid_direction["analysis_mode"] = "three_axis_v15"
        invalid_direction["metrics"]["cost"]["direction"] = 1
        invalid_direction_path = temp_path / "invalid-direction.json"
        invalid_direction_path.write_text(json.dumps(invalid_direction) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(invalid_direction_path), "--representatives", str(reps), expect=1)

        placeholder = json.loads(config_path.read_text(encoding="utf-8"))
        placeholder["adjustments"] = [{"model":"Alpha", "metric":"cost", "multiplier":0.5, "mode":"normal", "effective_date":"2026-07-30", "source_url":"https://vendor.invalid/placeholder", "provenance_status":"reviewed"}]
        placeholder_path = temp_path / "placeholder-source.json"
        placeholder_path.write_text(json.dumps(placeholder) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(placeholder_path), "--representatives", str(reps), expect=1)

        missing_protocol = json.loads(config_path.read_text(encoding="utf-8"))
        missing_protocol["analysis_mode"] = "three_axis_v15"
        missing_protocol["mds"].pop("distance_space")
        missing_protocol_path = temp_path / "missing-mds-protocol.json"
        missing_protocol_path.write_text(json.dumps(missing_protocol) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(missing_protocol_path), "--representatives", str(reps), expect=1)

        changed_protocol = json.loads(config_path.read_text(encoding="utf-8"))
        changed_protocol["analysis_mode"] = "three_axis_v15"
        changed_protocol["mds"]["iterations"] = 1
        changed_protocol_path = temp_path / "changed-mds-protocol.json"
        changed_protocol_path.write_text(json.dumps(changed_protocol) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(changed_protocol_path), "--representatives", str(reps), expect=1)

        reduced = json.loads(config_path.read_text(encoding="utf-8"))
        reduced["analysis_mode"] = "reduced_2d"
        reduced["metrics"].pop("latency")
        reduced["pareto"] = {"axes":["performance", "cost"], "authoritative":False}
        reduced["mds"] = {"fit_ids":[], "excluded_ids":[], "projection_only_ids":[], "edge_source":"grid_adjacency"}
        reduced_path = temp_path / "reduced-2d.json"
        reduced_path.write_text(json.dumps(reduced) + "\n", encoding="utf-8")
        reduced_output = temp_path / "reduced-out"
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(reduced_path), "--output-dir", str(reduced_output))
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(reduced_path), "--representatives", str(reduced_output / "representatives.csv"))
        run(sys.executable, str(SCRIPTS / "compute_mds.py"), "--representatives", str(reduced_output / "representatives.csv"), "--config", str(reduced_path), "--output", str(temp_path / "reduced-mds.json"), expect=1)

        reduced_no_performance = json.loads(config_path.read_text(encoding="utf-8"))
        reduced_no_performance["analysis_mode"] = "reduced_2d"
        reduced_no_performance["metrics"].pop("performance")
        reduced_no_performance["pareto"] = {"axes":["cost", "latency"], "authoritative":False}
        reduced_no_performance["mds"] = {"fit_ids":[], "excluded_ids":[], "projection_only_ids":[], "edge_source":"grid_adjacency"}
        reduced_no_performance_path = temp_path / "reduced-cost-latency.json"
        reduced_no_performance_path.write_text(json.dumps(reduced_no_performance) + "\n", encoding="utf-8")
        no_performance_output = temp_path / "reduced-cost-latency-out"
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(reduced_no_performance_path), "--output-dir", str(no_performance_output))
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(reduced_no_performance_path), "--representatives", str(no_performance_output / "representatives.csv"))

        reduced_bad_mds = json.loads(reduced_path.read_text(encoding="utf-8"))
        reduced_bad_mds["mds"]["fit_ids"] = ["Alpha|base"]
        reduced_bad_mds_path = temp_path / "reduced-bad-mds.json"
        reduced_bad_mds_path.write_text(json.dumps(reduced_bad_mds) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(reduced_bad_mds_path), "--representatives", str(reduced_output / "representatives.csv"), expect=1)

        bad_reps = temp_path / "bad-representatives.csv"
        bad_rows = rows.copy()
        bad_rows[0]["performance_deviation_score"] = "999"
        with bad_reps.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=bad_rows[0].keys())
            writer.writeheader()
            writer.writerows(bad_rows)
        run(sys.executable, str(SCRIPTS / "validate_tradeoff_contract.py"), "--input", str(input_path), "--config", str(config_path), "--representatives", str(bad_reps), expect=1)

        bad_mds = temp_path / "bad-mds.json"
        bad_mds_data = json.loads(mds_path.read_text(encoding="utf-8"))
        bad_mds_data["pairs"][0]["original_distance"] = 999
        bad_mds.write_text(json.dumps(bad_mds_data) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_mds_scope.py"), "--input", str(input_path), "--config", str(config_path), "--mds", str(bad_mds), "--representatives", str(reps), expect=1)

        bad_mds_metadata = temp_path / "bad-mds-metadata.json"
        bad_mds_metadata_data = json.loads(mds_path.read_text(encoding="utf-8"))
        bad_mds_metadata_data["algorithm"] = "other"
        bad_mds_metadata.write_text(json.dumps(bad_mds_metadata_data) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_mds_scope.py"), "--input", str(input_path), "--config", str(config_path), "--mds", str(bad_mds_metadata), "--representatives", str(reps), expect=1)

        missing_mds_output_field = json.loads(mds_path.read_text(encoding="utf-8"))
        missing_mds_output_field.pop("distance_space")
        missing_mds_output_path = temp_path / "missing-mds-output-field.json"
        missing_mds_output_path.write_text(json.dumps(missing_mds_output_field) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "validate_mds_scope.py"), "--input", str(input_path), "--config", str(config_path), "--mds", str(missing_mds_output_path), "--representatives", str(reps), expect=1)

        missing_source = json.loads(input_path.read_text(encoding="utf-8"))
        missing_source.pop("selected_benchmarks")
        missing_source_path = temp_path / "missing-source-selection.json"
        missing_source_path.write_text(json.dumps(missing_source) + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(missing_source_path), "--config", str(config_path), "--output-dir", str(temp_path / "missing-source-out"), expect=1)

        mode_boundary = json.loads(config_path.read_text(encoding="utf-8"))
        mode_boundary["adjustments"] = [{"model":"Alpha", "metric":"latency", "multiplier":0.5, "mode":"fast"}]
        mode_path = temp_path / "mode-boundary.json"
        mode_path.write_text(json.dumps(mode_boundary) + "\n", encoding="utf-8")
        mode_output = temp_path / "mode-out"
        run(sys.executable, str(SCRIPTS / "compute_tradeoff_scores.py"), "--input", str(input_path), "--config", str(mode_path), "--output-dir", str(mode_output))
        standardized = json.loads((mode_output / "standardized.json").read_text(encoding="utf-8"))
        alpha_base = next(point for point in standardized["points"] if point["id"] == "Alpha|base")
        if alpha_base["benchmarks"]["Task A"]["latency"]["raw"] != alpha_base["benchmarks"]["Task A"]["latency"]["adjusted"]:
            raise RuntimeError("Fast-only adjustment leaked into normal-mode data")
    print("PASS: transfer, negative-config, and mode-boundary smoke tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
