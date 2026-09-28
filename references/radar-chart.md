# Benchmark radar chart

`scripts/build_radar_chart.py` produces a compact self-contained radar view from a calculator `standardized.json` file and its method JSON. It plots each selected benchmark as one axis and each model × effort candidate as one series, using the chosen metric's within-benchmark z score. The default metric is `performance`; a method may configure `radar.metric`, an explicit ordered `radar.benchmarks` subset, and/or `radar.candidate_ids`. When axes are omitted, the full `selected_benchmarks` order is used. Excluded benchmarks are always rejected.

The chart applies the method's `display_transform` to each z score (default `50 + 10z`, labeled in deviation-score points). A `z` transform is labeled in z-score units; other affine transforms include their formula in the display-unit label. A single radial domain is calculated from every configured candidate and does not change when readers toggle series. The domain includes padding around the full minimum and maximum, so negative z scores and extreme values remain visible. The accompanying table reports raw and adjusted values with their declared units, z scores, and display scores. Units may be declared by `metrics[metric].unit` or by the optional source input's benchmark `unit`, `units`, or `unit_by_field[field]`. The generator requires these declarations to agree and labels absent units `unspecified`.

For fewer than three axes the artifact shows a table-only fallback. Radar polygon area is not a ranking, and within-benchmark standardized results do not make different benchmarks' raw units directly comparable. Composite benchmarks, missing values, non-finite numbers, duplicate axes or IDs, and unknown configured candidates are rejected; no gaps are imputed.

## Reviewed text and generation

The generator has a two-step text workflow. Prepare and review the reader-facing canonical JSON first:

```sh
python scripts/build_radar_chart.py \
  --standardized outputs/v15/standardized.json \
  --config method.json \
  --input raw-input.json \
  --prepare-text outputs/radar-v1-text-draft.json
```

After review, pass that file as `--text` and choose a new output directory. Existing directories are never overwritten:

```sh
python scripts/build_radar_chart.py \
  --standardized outputs/v15/standardized.json \
  --config method.json \
  --input raw-input.json \
  --text outputs/radar-v1-text.json \
  --output-dir outputs/radar-v1
```

The versioned output contains `radar.json` (numeric values, transformation, units, axes, and fixed domain), `text.json` (the canonical visible-text source), and `radar.html` (self-contained responsive HTML/SVG). Static visible text and the checkbox accessible names carry JSON-pointer bindings into the embedded `canonical-text` object. The page includes keyboard- and pointer-operable candidate checkboxes, visible series styles that do not rely on color alone, and a horizontally scrollable chart and table on narrow screens.

Run focused checks with:

```sh
python3 evals/test_radar_chart.py
```
