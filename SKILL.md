---
name: model-effort-tradeoff-analysis
description: Compare model×effort configurations across benchmarks with auditable performance, cost, latency, Pareto trade-offs, and per-benchmark radar charts. Use for multi-benchmark analysis, benchmark updates with documented mode-specific adjustments, or interactive comparison artifacts; use a direct comparison for a single-benchmark fact.
---

# Model × Effort Trade-off Analysis

Turn benchmark records into a comparison that preserves raw values, provenance, and the calculation method. Show trade-offs and task-specific differences rather than collapsing candidates into one ranking, unless the user explicitly requests a separate decision rule.

## Choose the scope

- Use `three_axis_generic` for performance, cost, and latency across multiple benchmarks. Record normalization, representative, and display choices.
- Use `three_axis_v15` only to reproduce the fixed historical protocol. Read [v15-process.md](references/v15-process.md) and its configuration; do not transfer its model names, counts, adjustments, exclusions, or screen order to another analysis.
- Use `reduced_2d` when only two desirable metrics exist. State the missing metric, omit three-axis MDS, and do not claim three-dimensional Pareto status. Cross-task spread describes variation; it is not a substitute cost or latency axis.
- For a single-benchmark fact, answer directly. Do not impose an interactive artifact or the full validation workflow.

Read [data-and-method-schema.md](references/data-and-method-schema.md) before adapting JSON. Use [quickstart.md](references/quickstart.md) for executable fixture commands, [comparison-views.md](references/comparison-views.md) for multi-view artifacts, and [radar-chart.md](references/radar-chart.md) for benchmark radar charts.

## Calculation and provenance

1. Preserve the raw source and create a new output version. Keep source URLs, raw units, candidate IDs, selected/excluded benchmark names, and method configuration with the result.
2. Require unique candidate IDs and unique selected/excluded benchmark names. Exclude overlapping composite indices before normalization. Report missing cells; never fill a component using its excluded composite.
3. Standardize across candidates **within each benchmark**, using the declared SD denominator: `z = (value − mean) / SD`. Reverse cost/latency directions so higher derived scores mean more desirable values. Larger raw cost or latency is not better.
4. The default representative is the median across benchmark z values; the default display is `50 + 10z`. The generic calculator also supports sample SD, mean representatives, and a positive affine display transform. Record deviations explicitly. Log transforms require a separately reviewed implementation.
5. Measure task spread as the population SD of each candidate's benchmark performance z values, with its display scale recorded. Do not describe this as repeated-run stability or use it as another Pareto axis.
6. Apply declared official adjustments before standardization; retain raw and adjusted values. Verify potentially stale changes against first-party sources and record metric, mode, effective date, URL, and multiplier. Store considered-but-unapplied interventions separately with `applied: false` and a reason. A claim for one mode does not justify changing another mode or inventing a performance effect.

Run `compute_tradeoff_scores.py` and independently verify its output with `validate_tradeoff_contract.py`. Reject non-finite values. Zero SD has no defined z-score: resolve the protocol explicitly instead of silently substituting zero.

## Pareto, geometry, and benchmark profiles

- Define authoritative Pareto axes explicitly. Dominance means at least as desirable on every axis and strictly better on one. Preserve all candidates; a two-axis view of a three-axis analysis retains three-axis status.
- Fit metric MDS in configured internal representative z-space. Declare fit IDs, exclusions, and projection policy; report algorithm, initialization, iterations, tolerance, stress, and relative RMSE. The bundled three-axis calculator uses circle-initialized SMACOF in both supported three-axis modes. Another algorithm requires a separate reviewed implementation.
- Display rotation must preserve distances. MDS coordinates are unitless and encode neither rank nor causality. Reuse only fixed model×effort adjacency edges whose endpoints are in the fit; do not invent nearest-neighbor or MST edges.
- Include a **per-benchmark radar chart** in interactive benchmark comparisons. Each spoke is a selected benchmark in configured order; each series is a model×effort candidate. Use each benchmark's performance z-score transformed to the configured display scale, not the candidate's cross-benchmark representative. Other metrics may use separate charts with explicit direction and units.
- Keep one radial domain for all candidates regardless of selection; include all finite values without clipping. Provide candidate selection, non-color distinctions, and a raw/adjusted/derived-value table. Polygon area is not a ranking. With fewer than three benchmarks, use a table instead of a degenerate radar polygon.

## Text, interaction, and validation

For substantial reader-facing copy, read [text-and-review-contract.md](references/text-and-review-contract.md). Prepare canonical text JSON, review it, then generate from that exact source without fallback prose. Bind static HTML text to source keys and run `check_artifact_text.py`. A hash manifest detects changes after generation; it does not prove review occurred or runtime JavaScript displays only canonical text.

Explain desirable-direction scores and raw units in plain language before technical definitions. Keep reviewer disputes and release history outside the visualization.

Verify the requested flow, including rendered labels, values, candidate toggles, keyboard operation, and narrow-screen scrolling. For multi-view artifacts also test node/edge details and 3D rotation versus page scrolling. Report calculation, static HTML, desktop browser, emulated mobile, and real-device coverage separately.

When independent review is requested, use the specified reviewer with isolated context, current requirements, raw artifacts, and evidence. Accept reproducible defects and requirement-backed changes; reject scope expansion with a reason. Use [review-adjudication-template.md](references/review-adjudication-template.md) to record findings and the exit decision. Create a versioned checkpoint before a long, external, destructive, or explicitly resumable review.

## Deliverables and tools

For analysis, retain raw input, method, standardized and representative data, and applicable Pareto/MDS diagnostics. For an interactive artifact, also retain self-contained HTML, canonical text, radar data, relevant grid edges, and validation evidence. A radar-only request does not require unrelated views. Preserve earlier versions.

Scripts are in `scripts/` and use Python's standard library:

| Task | Tools |
|---|---|
| Calculate and independently check scores | `compute_tradeoff_scores.py`, `validate_tradeoff_contract.py` |
| Check the three-axis Pareto set | `validate_pareto.py` |
| Build and validate fixed adjacency | `build_grid_edges.py`, `build_mds_edges.py`, `validate_grid_edges.py` |
| Compute and check MDS | `compute_mds.py`, `validate_mds_scope.py` |
| Generate benchmark radar HTML and data | `build_radar_chart.py` |
| Check canonical static copy and post-generation integrity | `check_artifact_text.py`, `write_artifact_manifest.py` |
| Migrate legacy v15 methods into new files | `migrate_v15_method.py` |

Run `python3 evals/run_smoke.py` for numerical regressions, `python3 evals/test_artifact_text.py` for static-copy validation, and `python3 evals/test_radar_chart.py` for radar regressions. Use [evals/cases.jsonl](evals/cases.jsonl) and [evals/rubric.md](evals/rubric.md) for realistic activation, transfer, and interaction checks; automated tests alone do not establish skill-selection or browser correctness.
