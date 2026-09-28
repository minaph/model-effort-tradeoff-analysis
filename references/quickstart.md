# Executable fixture workflow

Run from the skill repository root with Python 3.10 or later. The scripts use only the standard library. These fixtures contain synthetic data; their results do not describe real models. Choose a new output directory for each run so earlier artifacts remain available.

## Calculate and validate

```sh
RUN_DIR=$(mktemp -d "${TMPDIR:-/tmp}/model-effort-example.XXXXXX")
python3 scripts/compute_tradeoff_scores.py \
  --input evals/fixtures/transfer_input.json \
  --config evals/fixtures/transfer_config.json \
  --output-dir "$RUN_DIR/scores"
python3 scripts/validate_tradeoff_contract.py \
  --input evals/fixtures/transfer_input.json \
  --config evals/fixtures/transfer_config.json \
  --representatives "$RUN_DIR/scores/representatives.csv"
```

Outputs include `standardized.json`, `representatives.csv`, and `summary.json`. The validator independently recomputes representative values. For a radar-only task, continue directly to the radar section. A full comparison may also use:

```sh
python3 scripts/build_grid_edges.py \
  --input evals/fixtures/transfer_input.json \
  --config evals/fixtures/transfer_config.json --output "$RUN_DIR/grid.json"
python3 scripts/compute_mds.py \
  --representatives "$RUN_DIR/scores/representatives.csv" \
  --config evals/fixtures/transfer_config.json --output "$RUN_DIR/mds.json"
python3 scripts/build_mds_edges.py --grid-edges "$RUN_DIR/grid.json" \
  --config evals/fixtures/transfer_config.json --output "$RUN_DIR/mds-edges.json"
python3 scripts/validate_grid_edges.py \
  --input evals/fixtures/transfer_input.json \
  --config evals/fixtures/transfer_config.json \
  --edges "$RUN_DIR/grid.json" --mds-edges "$RUN_DIR/mds-edges.json"
python3 scripts/validate_mds_scope.py \
  --input evals/fixtures/transfer_input.json \
  --config evals/fixtures/transfer_config.json \
  --representatives "$RUN_DIR/scores/representatives.csv" --mds "$RUN_DIR/mds.json"
```

The fixture smoke test also builds and independently checks a Pareto set. The radar generator below supplies the benchmark-profile view, not a complete implementation of every comparison view.

## Prepare, review, and render radar text

```sh
python3 scripts/build_radar_chart.py \
  --standardized "$RUN_DIR/scores/standardized.json" \
  --config evals/fixtures/transfer_config.json \
  --input evals/fixtures/transfer_input.json \
  --prepare-text "$RUN_DIR/radar-text.json"
```

Read and review `radar-text.json` before the next command. It contains explanatory copy, benchmark labels, candidate labels, and formatted values. Verify wording against the raw records and method. The fixture has no raw unit metadata, so the table explicitly reports unspecified units; real analyses should supply them as described in [radar-chart.md](radar-chart.md). Review is an agent/human judgment, not something the generator or a hash proves.

```sh
python3 scripts/build_radar_chart.py \
  --standardized "$RUN_DIR/scores/standardized.json" \
  --config evals/fixtures/transfer_config.json \
  --input evals/fixtures/transfer_input.json \
  --text "$RUN_DIR/radar-text.json" --output-dir "$RUN_DIR/radar-v1"
python3 scripts/write_artifact_manifest.py \
  --artifact "$RUN_DIR/radar-v1/radar.html" \
  --output "$RUN_DIR/radar-v1/manifest.json"
printf '[]\n' > "$RUN_DIR/forbidden.json"
python3 scripts/check_artifact_text.py \
  --canonical "$RUN_DIR/radar-v1/text.json" \
  --generated "$RUN_DIR/radar-v1/radar.html" \
  --root "$RUN_DIR/radar-v1" --forbidden "$RUN_DIR/forbidden.json" \
  --integrity-manifest "$RUN_DIR/radar-v1/manifest.json"
```

The output directory contains `radar.html`, `radar.json`, and `text.json`. Open `radar.html` in a browser; no server or network request is needed. Toggle a candidate by pointer and keyboard, verify the plotted series and table, and inspect desktop and narrow viewports. Confirm the radial domain is unchanged when selection changes. Keep runtime coverage separate from the static text check. Publishing an artifact remains subject to the user's authorization; generating it does not grant publication permission.

## Regression checks

```sh
python3 evals/run_smoke.py
python3 evals/test_artifact_text.py
python3 evals/test_radar_chart.py
```

The v15 smoke input is synthetic and tests contract behavior. It does not reproduce the historical source dataset or validate current vendor claims. For a real v15 reproduction, supply the original raw records and verified provenance rather than treating synthetic fixture values as historical evidence.
