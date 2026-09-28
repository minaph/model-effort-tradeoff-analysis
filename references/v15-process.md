# v15 process reference

This reference records the concrete process from the GPT 5.6 comparison. Its names, counts, URLs, and thresholds define the fixed `three_axis_v15` reproduction branch. For another comparison, select `three_axis_generic` and supply that comparison's own configuration; do not edit historical constants while retaining the v15 label.

## v15 calculation choices

- Start with 19 model×effort candidates and nine benchmark records.
- Exclude Artificial Analysis Intelligence Index v4.1 and Artificial Analysis Coding Agent Index v1.1 before any scoring because they overlap with component benchmarks.
- Use seven benchmarks: Agents' Last Exam, GDPval-AA v2, DeepSWE v1.1, Terminal-Bench 2.1, BrowseComp, OSWorld 2.0, and AutomationBench.
- Standardize each metric across the 19 candidates within each benchmark. Use population SD, no log transform, performance unchanged, cost and latency sign-flipped.
- Take the median across the seven benchmark z values for each of performance, cost, and latency.
- Display deviation scores `50 + 10z`; preserve raw values beside them. Compute task spread as the population SD of the seven performance z values × 10, outside the Pareto axes.
- In the structured `three_axis_v15` method, population SD, median representatives, `50 + 10z`, and task-spread scale 10 are fixed contract values. A different three-axis protocol must use `three_axis_generic` instead of silently relabeling itself v15.
- Apply official cost multipliers Luna ×0.20 and Terra ×0.80. Record Sol’s Fast-mode speed claim as a structured `applied: false` intervention and do not apply it to normal-mode latency; the reason must say that normal-mode latency remains unchanged. State both choices in the method text and HTML.

## v15 authoritative Pareto/MDS contract

The authoritative Pareto status is three-dimensional: performance, cheapness, and speed. The 2D trade-off view keeps this 3D status; it does not create a second 2D Pareto set.

The MDS fit contains the independently recomputed 14 three-dimensional Pareto points plus GPT-5.6 Sol / max as a same-weight anchor, for 15 points. The structured method records `anchor_ids`, `expected_pareto_count`, and `excluded_model_names`; validators derive the fit and exclusion sets from the representative values and input candidates rather than trusting only the declared fit list. The four GPT-5.5 points have no MDS distance, coordinate, Shepard pair, or drawing. There are no projection-only points. Fit metric MDS in the three-representative internal-z space, using the v15 circle-initialized SMACOF loop (2400 iterations, convergence tolerance `1e-13`), then apply only a display rotation so Terra appears approximately horizontal with Terra low toward the left. Stress is the square root of the sum of squared pairwise distance residuals; relative RMSE divides that by the square root of the sum of squared target distances. The 29 fixed-grid edges are filtered to the 15-point fit and boundary policy, leaving 22 MDS edges; no coordinate-derived edges are created.

MDS lines reuse fixed-grid adjacency. They are not nearest-neighbor, MST, or spatial-distance edges. In v15, boundary edges between GPT-5.5 and GPT-5.6 Luna remain in the grid as dashed edges but are omitted from the MDS display to reduce clutter. The method record reports fit count 15, excluded count 4, projection-only count 0, 105 Shepard pairs, stress about `0.5699823668687`, and relative RMSE about `0.02310783019328`; the last floating-point digits may vary between equivalent implementations.

## v15 visual contract

The reader-facing order is:

1. トレードオフ図
2. 3指標の分布
3. 3次元プロット
4. 候補の距離マップ
5. 遷移グリッド
6. 距離マップの確かめ方
7. 性能とタスク別の得意不得意

This is the archived seven-view order. New interactive comparisons also include a benchmark radar view, preferably beside task-specific differences. The radar addition does not change the v15 numerical contract or claim that the archived artifact already contained it. Its spokes are the seven selected benchmarks, with per-benchmark performance scores rather than cross-benchmark medians; follow [radar-chart.md](radar-chart.md).

The grid uses effort low → medium → high → xhigh → max from left to right and model GPT-5.5 → Luna → Terra → Sol from bottom to top. Shapes are max=●, high=◆, medium=■, low=▲, xhigh=⬢; actual SVG geometry is preferred to fragile Unicode glyph rendering. Model color and effort shape are both required.

Every node, label, edge, and difference box has a usable hit area. Edge/difference-box selection shows the ordered transition and all three deviation-score-point differences. Node selection shows the raw benchmark value and deviation score in the detail table. Arbitrary nonadjacent A/B selection was removed. The raw seven-benchmark download is placed at the page top.

## v15 review lessons

The first final review was NO-GO because the generator retained a fallback text source and the validator expected no hover arrow although the current requirement allowed hover/click arrows. The fix made the reviewed text JSON the sole text input, compared embedded text exactly, and changed the validator to check the actual hover-arrow contract. Re-review was PASS/GO.

The archived v15 method file is a reader-facing legacy format: it contains prose keys such as `z_definition` and `grid_edges`, but not the structured `metrics`, `standardization`, and `mds.fit_ids` contract. Use `scripts/migrate_v15_method.py` to create a new structured config, then fill and review missing adjustment source URLs/dates; do not pass the legacy file directly to the calculator or overwrite it.

Likewise, the archived v15 edge JSON has a legacy `mds_edges` field made by dropping only boundary edges, so it still contains three GPT-5.5-internal edges. Treat `edges` as the 29-edge grid source, then run `scripts/build_mds_edges.py` with the structured fit scope to produce the 22-edge MDS subset.

The reviewer’s requests to hide all non-Pareto MDS labels/edges/boxes and to map GPT-5.5 to the MDS surface were obsolete after later user corrections. The final artifact removed those descriptions rather than preserving them as historical UI instructions.
