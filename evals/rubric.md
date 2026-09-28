# Evaluation rubric

## Activation

The skill should activate for a multi-candidate, multi-benchmark model/configuration comparison when the user needs trade-offs, reproducibility, an interactive artifact, or an independent review. It should not force the full workflow for a single-benchmark pairwise fact.

## Calculation gates

- Composite indicators are excluded before any normalization.
- Duplicate selected/excluded benchmark names are rejected in both input and method files. Pareto validation rejects non-finite values on every axis.
- The standardization population and denominator are explicit; the v15 origin uses population SD and no log transform.
- Desirability directions, official adjustments, raw-versus-adjusted values, representative medians, display conversion, and task spread are independently checkable.
- Task spread is not silently promoted to a Pareto axis.
- The authoritative Pareto dimension is explicit. A 2D view does not silently replace a configured 3D status.
- In `three_axis_v15`, the score protocol is fixed and the MDS fit is independently checked as Pareto IDs union the declared anchor, with declared exclusions and no projection-only IDs. A different three-axis protocol uses `three_axis_generic`.

## Geometry and interaction gates

- Fixed-grid edges are derived only from configured adjacent model/effort order and directed forward.
- MDS coordinates, fit scope, exclusions, projection-only points, stress, and error are reported.
- MDS edges are reused grid edges, never nearest-neighbor, MST, or spatial-distance edges.
- Every rendered SVG hit target is testable; mobile scroll and 3D gesture coverage are reported honestly.
- Radar spokes are selected benchmarks in method order, and scores are per-benchmark derived values. Candidate toggles leave scores and radial bounds unchanged; raw/adjusted values and units remain available in a table.
- Negative or extreme finite radar scores are not clipped. Fewer than three benchmarks produce an explicit table-only fallback. Polygon area is never a ranking.

## Text and review gates

- Reader-facing text is generated from one reviewed structured source.
- Embedded JSON equality alone does not pass: bound static text and supported UI attributes must match canonical keys. Runtime JS and template content require separate rendered checks; a hash only detects post-generation changes.
- Plain-language explanation precedes formulas and technical caveats.
- Raw units and derived display units are not conflated.
- Reviewer feedback is adjudicated against the current requirement set; valid defects are fixed and contradictory or purely preference-based demands are recorded as overreach.

## Transfer and anti-overfitting

The v15 names and counts are fixed only inside the explicit `three_axis_v15` protocol. A transferred case with different models, efforts, benchmark count, or official adjustment rules should use `three_axis_generic` and preserve the workflow while changing the configuration. A near-miss single-fact request should remain lightweight.

Run `python evals/run_smoke.py` for the bundled transfer fixture. It exercises generic three-axis computation, input/contract validation, fixed-grid validation, MDS scope, Pareto recomputation, v15 score-protocol rejection, rejection of an unsupported `raw` display transform, and the Fast-only mode boundary. The declarative cases remain the review rubric; the fixture is a small executable regression, not a replacement for visual review.

Also run `python3 evals/test_artifact_text.py` and `python3 evals/test_radar_chart.py`. Use [../references/quickstart.md](../references/quickstart.md) to generate a reviewable radar fixture. In a browser, toggle a candidate with mouse and keyboard, compare displayed table values to the fixture, inspect desktop and narrow viewports, and distinguish viewport emulation from real-device testing. Use the near-miss and transfer prompts in `cases.jsonl` for an independent agent trial when evaluating routing behavior; do not count script tests as a measured activation success rate.
