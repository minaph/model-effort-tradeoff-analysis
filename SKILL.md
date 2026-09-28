---
name: model-effort-tradeoff-analysis
description: Build an auditable model×effort benchmark comparison that exposes performance, cost, latency, task variation, Pareto trade-offs, MDS relationships, and fixed-grid transitions instead of collapsing candidates into one ranking. Use when comparing model configurations across benchmarks, updating stale benchmark data with official price or mode interventions, generating a self-contained interactive HTML, or reviewing an existing model×effort comparison.
---

# Model × Effort Trade-off Analysis

## Core job

Turn benchmark records for model×effort candidates into an auditable, mobile-first comparison artifact. Preserve raw values and provenance, normalize only within benchmarks, expose performance/cost/latency trade-offs and task differences, and make every derived view agree with one calculation contract.

Do not produce a single “best model” score unless the task explicitly requests a separate decision rule. The default output is a decision surface for choosing configurations under different priorities.

## Scope gate

Use this skill when the task has model/configuration candidates, multiple benchmark measures, and at least two of performance, cost, latency, or cross-task variation. Trigger the `three_axis_v15` branch for the concrete v15 protocol below. For a genuinely different three-axis protocol, use the explicit `three_axis_generic` branch and record its choices; do not label it v15. If only two desirable axes exist, use the reduced two-axis branch: do not claim a three-dimensional Pareto set or v15 MDS fit, and make the missing axis and reduced scope explicit.

Use a lighter analysis for a single benchmark or a simple pairwise fact. Delegate domain-specific benchmark interpretation, legal/medical claims, or generic web/app design to the relevant skill; this skill owns the comparison contract and its audit trail.

## Task configuration

Before calculating, make these values explicit in a machine-readable method file:

- candidate schema: stable `id`, `model`, `effort`, raw benchmark records, and model/effort display order;
- selected benchmarks and input-stage exclusions, especially composite indices that overlap with component benchmarks;
- metric fields, units, desirability direction, missing-value policy, and whether any transform is allowed;
- official post-publication adjustments: source URL, date, affected model/mode/metric, multiplier, and untouched metrics;
- representative method, variability definition, Pareto axes, and display transform;
- MDS `fit_ids`, explicitly excluded IDs, projection-only IDs, display rotation, and which grid edges may be reused;
- output version, review roles, and environment coverage.

If a value is not specified, choose a defensible default and record it. Never infer a mode-specific intervention from a different mode.

## Calculation contract

### Input and provenance

1. Preserve the source data and write a new version; never overwrite an existing HTML or checkpoint.
2. Exclude composite benchmarks before standardization. Do not use excluded values to fill component values.
3. Require one raw record for every selected benchmark × candidate × metric, or report the missing cells explicitly. Do not silently impute.
4. Keep benchmark descriptions, raw units, source URLs, adjustment evidence, and calculation method separate from reader-facing prose.
5. If the attached or published data may be stale, verify post-publication changes against first-party documentation. Record the affected mode, effective date, source URL, and multiplier; for a considered-but-unapplied intervention also record structured `applied: false` and a reason that names the unaffected mode as unchanged. A claim for one mode does not authorize changing another mode.

### Direction and standardization

For each selected benchmark and metric, standardize across candidates in that benchmark only:

`z = (value − benchmark mean) / benchmark SD`

Use the population SD (denominator `n`) for the v15 protocol. Keep the internal z values for calculation and use no log transform unless the task configuration explicitly changes the protocol. Leave performance positive; multiply cost and latency by −1 so higher is desirable. This sign reversal is a calculation convention, not a claim that raw cost or raw latency is high-is-good.

The bundled calculator supports only explicit, reviewed choices in `three_axis_generic`: population or sample SD, median or mean representative, and `z` or an explicit affine display transform. In `three_axis_v15`, the validator and calculator must reject any deviation from population SD, median representatives, `50 + 10z`, and performance spread scaled by 10; it must never silently reinterpret a conflicting method file.

Apply declared official cost or mode adjustments before standardization and retain both raw and adjusted values. If an official speed improvement is limited to Fast mode, do not apply it to normal-mode latency. If no before/after benchmark exists, trust only the declared adjustment for the affected metric and do not invent performance effects.

### Representatives and variability

- Use the median of the selected benchmark z values as each candidate’s representative for performance, cost, and latency.
- When the reader needs simpler values, display deviation scores `50 + 10z`; call differences “deviation-score points,” not physical units.
- Show raw values beside the corresponding deviation score in detail tables, with raw units explicitly stated.
- Compute task variation as the population SD of the candidate’s selected performance z values. Treat it as task-specific strengths/weaknesses or performance spread, not as temporal stability and not as a fourth Pareto axis.

### Pareto and MDS

- Define the authoritative Pareto set in the three desirable axes: performance, cost/cheapness, and latency/speed.
- Candidate B dominates A when B is at least as high on all three axes and strictly higher on at least one. Preserve every candidate in plots; use opacity or an explicit status to distinguish non-Pareto points.
- A 2D trade-off chart may select two axes, but must retain the 3D Pareto status. Do not recompute a separate 2D Pareto set unless the task explicitly asks for a second analysis.
- Compute metric MDS from the configured representative 3-axis space. Fit scope must be explicit. For the v15 protocol, fit the 3D Pareto set plus the configured Sol/max anchor with equal weight, exclude GPT-5.5 from distance, coordinates, Shepard pairs, and drawing, and create no projection-only points.
- Record the MDS algorithm, initialization, iterations, tolerance, stress definition, and relative-RMSE definition. For the v15 protocol, use the bundled circle-initialized SMACOF implementation; do not silently replace it with a library default whose diagnostics differ.
- The bundled calculator also uses that fixed MDS protocol for `three_axis_generic` transfer fixtures. If a generic case needs a different MDS algorithm or convergence contract, define and review a separate implementation instead of relabeling its output as v15.
- A post-fit 2D rotation may improve readability, but must not alter distances. State that MDS coordinates are unitless and do not encode rank, direction, or causality.
- Reuse fixed-grid adjacency in MDS only where the configured endpoints have coordinates. Never create MDS edges from nearest neighbors, an MST, or spatial proximity. Report stress, relative RMSE, pair count, fit count, exclusions, and projection-only count.

## Visualization and interaction contract

Use the v15 view order unless the task gives a reason to change it:

1. `Trade-off chart`: selectable performance/cost/speed axes, full candidate set, authoritative 3D Pareto opacity.
2. `Histograms`: performance, speed, and cheapness on aligned scales; deviation-score 50 must be visible and centered.
3. `3D plot`: interactive rotation, all candidates, 3D Pareto status, model color plus effort shape/size.
4. `Distance map`: MDS points and the configured grid-adjacency edges, not spatially inferred edges.
5. `Transition grid`: fixed model×effort graph.
6. `Shepard plot`: original distance versus MDS distance, with stress and relative RMSE.
7. `Performance and task differences`: performance representative against cross-benchmark performance spread.

For the fixed grid, place effort left-to-right in the configured order and model bottom-to-top in the configured order. Create nodes only for existing combinations. Connect only adjacent effort or adjacent model combinations, with direction determined by the fixed order. Keep boundary styling and edge visibility configuration-driven; never let a later MDS layout redefine grid adjacency.

Make model color and effort shape independently legible. Give nodes, labels, edge strokes, and compact difference boxes real pointer hit areas. A node click opens benchmark detail; an edge or its difference box opens the fixed ordered transition and `Δ = B − A` details. Do not retain arbitrary A/B selection if the current task has removed it. Hover/click arrow behavior must match the current task contract and the validator.

Design for narrow screens first. Preserve readable chart dimensions with horizontal scrolling where needed; do not shrink or crop content to hide overflow. For draggable 3D views, provide an explicit rotation mode or gesture rule so page scrolling remains possible.

## Reader-facing text contract

Aggregate visible prose, takeaways, labels, and method explanations into one reviewed structured text source when the artifact has substantial copy. Review that source alone, then generate the HTML from it as the sole source—no fallback copy. Compare the embedded/generated text to the reviewed source.

Explain in plain language first: higher deviation score means more desirable direction, “cheapness” means lower cost, and Pareto analysis formalizes the idea of an upper substitute. Follow with technical definitions, exclusions, missing data, population SD, median, adjustments, MDS fit scope, and units. Label cross-task spread according to what it measures; do not call it stability unless repeated-run stability was actually measured. Keep edit history and reviewer disputes out of the public visualization; store them in release/review records.

## Review and validation workflow

1. Run deterministic calculations and independently recompute the excluded benchmarks, selected count, direction reversal, median, population SD, 3D Pareto set, grid edges, edge directions, and MDS fit scope.
2. If visible text is substantial, give only the text aggregate to a text reviewer first. Integrate accepted wording changes and verify canonical-source equality.
3. Use an independent reviewer with the task-specified model/effort and an isolated context when requested. Pass current requirements and raw artifacts, not the intended diagnosis.
4. Treat reviewer feedback as evidence. Accept reproducible defects or requirement-backed changes; reject proposals that contradict explicit requirements; record both decisions and any overreach.
5. Inspect every rendered graph visually. Run node/edge interaction smoke and 3D gesture smoke. Distinguish calculation, static-render, VM, real-browser, and mobile-device coverage in the report.
6. Create a versioned checkpoint before a long, external, destructive, difficult-to-reproduce, or explicitly resumable review. A short synchronous review of easily reproducible work does not require an archival checkpoint.

## Required deliverables

When an interactive artifact is requested, produce the self-contained HTML plus machine-readable raw input, standardized/representative data, Pareto results, grid edges, MDS method/diagnostics, text source, and calculation method. For an analysis-only request, the HTML is optional but the machine-readable calculation and diagnostics remain required. Preserve source URLs and official intervention adjustments in the method record. Use a new version name and retain earlier checkpoints.

## Resources and scripts

- Read `references/v15-process.md` for the concrete v15 protocol, exact UI conventions, and origin failure cases.
- Read `references/data-and-method-schema.md` before adapting the input/output JSON schema.
- Read `references/text-and-review-contract.md` when visible prose, mobile interaction, or independent review matters.
- Use `references/review-adjudication-template.md` for the non-public finding ledger and exit decision.
- Use `scripts/compute_tradeoff_scores.py` for deterministic within-benchmark standardization, directional scores, medians, and population performance spread.
- Use `scripts/migrate_v15_method.py` when an older v15 method JSON lacks the structured `metrics`/`standardization`/`mds` keys; keep the old file unchanged and review the migrated config.
- Use `scripts/compute_mds.py` for deterministic metric MDS coordinates, pair distances, stress, and relative RMSE.
- Use `scripts/build_grid_edges.py` to generate fixed adjacent edges from configured order, then validate them; do not hand-author or infer them from MDS.
- Use `scripts/build_mds_edges.py` to filter those fixed edges to MDS fit endpoints and the configured boundary policy; never recompute MDS edges from coordinates.
- Use `scripts/validate_grid_edges.py` to verify fixed adjacency and direction; never infer edges from MDS.
- Use `scripts/validate_mds_scope.py` to verify fit/exclusion/projection sets and, when available, coordinate and Shepard identifiers.
- Use `scripts/validate_tradeoff_contract.py` and `scripts/check_artifact_text.py` before release.
- Use `scripts/write_artifact_manifest.py` immediately after generation and pass its immutable hash manifest to `check_artifact_text.py`; this catches visible HTML appended after canonical generation.
- Use `scripts/validate_pareto.py` to independently recompute the authoritative three-axis Pareto set.
- Read `evals/cases.jsonl` and run at least the v15 regression, a transfer case, and a near-miss case for a new use.
