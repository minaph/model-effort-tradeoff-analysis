# Data and method schema

Use a stable, explicit schema so the HTML, machine-readable outputs, and reviewer can refer to the same candidates and transformations.

## Input JSON

```json
{
  "selected_benchmarks": ["Benchmark A", "Benchmark B"],
  "excluded_benchmarks": ["Composite Index"],
  "points": [
    {
      "id": "Model A|medium",
      "model": "Model A",
      "effort": "medium",
      "raw": {
        "Benchmark A": {
          "performance": 0.73,
          "cost": 1.25,
          "latency_min": 2.4,
          "source_metric": "official-or-raw-field"
        }
      }
    }
  ]
}
```

Each selected benchmark must have the configured fields for every candidate. Candidate IDs and each selected/excluded benchmark list must be unique; duplicated names are errors, not implicit weights. Keep benchmark category, group, source metric, raw units, and provenance when available. Never use an excluded composite to reconstruct a missing component.

## Method JSON

At minimum include. Use `three_axis_v15` only for the fixed v15 score and MDS contract; use `three_axis_generic` for a different three-axis protocol, and `reduced_2d` when only two desirable axes are available:

```json
{
  "analysis_mode": "three_axis_v15",
  "candidate_count": 19,
  "version": "v15",
  "selected_benchmarks": [],
  "excluded_benchmarks": [],
  "model_order": [],
  "effort_order": [],
  "metrics": {
    "performance": {"field": "performance", "direction": 1},
    "cost": {"field": "cost", "direction": -1},
    "latency": {"field": "latency_min", "direction": -1}
  },
  "standardization": {"scope": "within_benchmark", "sd": "population", "log_transform": false},
  "missing_value_policy": "error",
  "representative": "median",
  "display_transform": "50 + 10z",
  "variability": {"metric": "performance", "stat": "population_sd", "display_scale": 10},
  "adjustments": [],
  "pareto": {"axes": ["performance", "cost", "latency"], "authoritative": true},
  "mds": {
    "fit_ids": [],
    "anchor_ids": [],
    "expected_pareto_count": 0,
    "excluded_model_names": [],
    "excluded_ids": [],
    "projection_only_ids": [],
    "edge_source": "grid_adjacency",
    "distance_method": "metric_mds",
    "algorithm": "v15_smacof_circle",
    "iterations": 2400,
    "tolerance": 1e-13,
    "distance_space": "internal_z",
    "stress_definition": "sqrt(sum of squared pairwise distance residuals)",
    "relative_rmse_definition": "sqrt(sum residuals squared) / sqrt(sum target distances squared)",
    "distance_axes": ["performance_z_median", "cost_z_median", "latency_z_median"]
  }
}
```

Do not rely on a prose sentence as the only record of a numerical choice. The HTML may present a plain-language explanation, but the method JSON must retain the exact values and lists.

## Derived outputs

Produce, as applicable:

- raw selected-benchmark JSON;
- standardized metric JSON containing benchmark mean, population SD, direction, adjusted raw value, and z;
- representative CSV with candidate, model, effort, three deviation scores, and performance spread;
- 3D Pareto IDs;
- fixed grid edges with `from`, `to`, `type`, and `boundary`;
- MDS coordinates and Shepard pairs with fit/exclusion metadata;
- reviewed text JSON;
- benchmark radar JSON with ordered benchmark axes, per-candidate per-benchmark values, and a shared radial domain when a radar view is requested;
- self-contained HTML and a validation report.

For radar-specific configuration, units, and text bindings, see [radar-chart.md](radar-chart.md). Radar values come from each standardized benchmark record rather than the cross-benchmark representative CSV. With fewer than three selected benchmarks, retain the value table and report the table-only fallback.

For a mode-specific intervention that was considered but not applied, record `applied: false`, the affected mode, and a reason that says the unaffected mode remains unchanged. Do not encode this decision only in prose.

## Validation invariants

- Candidate IDs are unique and every edge endpoint exists.
- Selected and excluded benchmark lists contain no duplicates, and their sets are disjoint.
- Every selected metric has the expected candidate count or an explicit missing-value report.
- Cost and latency direction changes are visible in method metadata.
- Population SD uses denominator `n`; performance spread is not a Pareto axis.
- Deviation score is an affine display of internal z and does not change Pareto or MDS ordering.
- 2D plot opacity matches the authoritative 3D Pareto status.
- MDS fit/exclusion/projection lists match the displayed coordinates and Shepard pairs.
- MDS distances use the internal representative z columns, not the reader-facing `50 + 10z` display scale; an affine display transform must not alter the fit geometry.
- Grid edges are only adjacent in the configured order and are directed from earlier to later order.
- All Pareto axes must be finite; `NaN` and positive/negative infinity are invalid input, not incomparable candidates.
- Radar spokes follow selected benchmark order; changing visible candidates must not change scores or radial bounds.
