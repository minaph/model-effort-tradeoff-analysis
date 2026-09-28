# Comparison views

Choose views that answer the user's question. The historical v15 order is in [v15-process.md](v15-process.md); it is not the default layout for every transferred analysis.

| View | What it explains |
|---|---|
| Trade-off scatter | Performance, cost, or speed pairs while retaining authoritative Pareto status |
| Metric distributions | Candidate distributions on aligned derived-score scales, with the display baseline visible |
| Three-axis plot | Three desirable axes, all candidates, and authoritative Pareto status |
| Distance map | MDS relationships and filtered fixed-grid edges, with fit scope and diagnostics |
| Transition grid | Existing model×effort combinations and adjacent ordered changes |
| Shepard plot | Original versus embedded distances, stress, and relative RMSE |
| Performance and task spread | Representative performance against cross-benchmark spread, not temporal stability |
| Benchmark radar | Benchmark-specific profiles and a raw, adjusted, and derived-value table |

For radar construction, scaling, and the table fallback for fewer than three benchmarks, read [radar-chart.md](radar-chart.md). Do not substitute three aggregate metrics for benchmark spokes.

## Fixed adjacency and interaction

Place effort left-to-right and model bottom-to-top in configured order. Create nodes only for existing combinations. Connect adjacent configured efforts or models only, directed from earlier to later order. Missing combinations do not justify jumping over configured levels. Keep boundary styles and visibility configuration-driven; MDS layout must not redefine adjacency.

Use model color plus effort shape or another independent non-color encoding. Give nodes, labels, edges, and difference boxes usable pointer targets. Node selection opens benchmark details. Edge selection shows the fixed ordered transition `A → B`, with `Δ = B − A` and declared units. Do not add arbitrary nonadjacent A/B selection when the task excludes it. Hover/click arrow behavior follows current requirements.

On narrow screens preserve legibility using contained horizontal scrolling where needed. A 3D rotation mode must allow ordinary page scrolling. Radar selection must work with keyboard as well as pointer and must not recompute the normalization population or radial scale.
