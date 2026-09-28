#!/usr/bin/env python3
"""Build a self-contained benchmark radar chart from standardized data.

The chart compares model × effort candidates on one configured metric across
benchmarks. It uses the benchmark-level z values from standardized.json and
keeps the display domain fixed across candidate selection.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from pathlib import Path
from typing import Any


DEFAULT_TEXT: dict[str, Any] = {
    "title": "Benchmark radar chart",
    "subtitle": "Each axis is one benchmark; each line is one model and effort setting.",
    "chart_heading": "Benchmark comparison",
    "series_heading": "Candidates to show",
    "table_heading": "Values by candidate and benchmark",
    "candidate_heading": "Candidate",
    "benchmark_heading": "Benchmark",
    "raw_heading": "Raw value",
    "adjusted_heading": "Adjusted value",
    "display_heading": "Display score",
    "z_heading": "Within-benchmark z",
    "interpretation": "A higher display score means a more desirable result for the selected metric. The default display score is 50 + 10 × z.",
    "unit_note": "Raw values retain each benchmark's declared unit. A unit marked unspecified was not provided by the source or method.",
    "radar_note": "Polygon area is not a ranking. Scores are standardized within each benchmark, so they do not make raw values from different benchmarks directly comparable.",
    "fallback_heading": "Radar view unavailable",
    "fallback_note": "A radar chart requires at least three benchmarks. The table below preserves the available results.",
    "score_suffix": "display score",
    "score_formula": "",
    "display_unit": "",
    "unit_unspecified": "unspecified",
    "axes": [],
    "ticks": [],
    "candidate_labels": {},
    "candidate_aria_labels": {},
    "table_rows": [],
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def display_parameters(value: Any) -> tuple[float, float]:
    if value == "z":
        return 0.0, 1.0
    if isinstance(value, dict):
        base, scale = finite_number(value.get("base"), "display_transform.base"), finite_number(value.get("scale"), "display_transform.scale")
    elif isinstance(value, str):
        match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*\+\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*[×*]?\s*z\s*", value)
        if not match:
            raise ValueError("display_transform must be 'z', '<base> + <scale>z', or {base, scale}")
        base, scale = float(match.group(1)), float(match.group(2))
    else:
        raise ValueError("invalid display_transform")
    if scale <= 0:
        raise ValueError("display_transform scale must be positive")
    return base, scale


def pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def fmt(value: float) -> str:
    return f"{value:.6g}"


def extract_unit(raw_input: dict[str, Any] | None, method: dict[str, Any], benchmark: str, metric: str) -> str:
    spec = method.get("metrics", {}).get(metric, {})
    method_unit = spec.get("unit") if isinstance(spec.get("unit"), str) and spec["unit"].strip() else None
    source_units = set()
    if raw_input:
        for point in raw_input.get("points", []):
            record = point.get("raw", {}).get(benchmark, {})
            declared = [record.get("unit")]
            units_field = record.get("units")
            if isinstance(units_field, dict):
                declared.append(units_field.get(spec.get("field")))
            else:
                declared.append(units_field)
            unit_by_field = record.get("unit_by_field", {})
            if isinstance(unit_by_field, dict):
                declared.append(unit_by_field.get(spec.get("field")))
            for candidate in declared:
                if isinstance(candidate, str) and candidate.strip():
                    source_units.add(candidate.strip())
    if len(source_units) > 1:
        raise ValueError(f"conflicting source raw units for {benchmark!r}: {sorted(source_units)}")
    if method_unit and source_units and method_unit.strip() not in source_units:
        raise ValueError(f"method and source raw units conflict for {benchmark!r}: {method_unit!r} vs {sorted(source_units)}")
    if method_unit:
        return method_unit.strip()
    return next(iter(source_units)) if source_units else "unspecified"


def build_data(standardized: dict[str, Any], method: dict[str, Any], raw_input: dict[str, Any] | None = None) -> dict[str, Any]:
    radar = method.get("radar", {})
    metric = radar.get("metric", "performance")
    metric_spec = method.get("metrics", {}).get(metric)
    if not isinstance(metric_spec, dict):
        raise ValueError(f"unknown radar metric: {metric!r}")
    available = list(standardized.get("selected_benchmarks", []))
    excluded = set(standardized.get("excluded_benchmarks", []))
    if list(method.get("selected_benchmarks", [])) != available:
        raise ValueError("standardized and method selected_benchmarks do not match in order")
    if set(method.get("excluded_benchmarks", [])) != excluded:
        raise ValueError("standardized and method excluded_benchmarks do not match")
    axes = list(radar.get("benchmarks", available))
    if len(axes) != len(set(axes)):
        raise ValueError("radar benchmarks contain duplicates")
    if set(axes) & excluded:
        raise ValueError("excluded/composite benchmarks cannot be radar axes")
    unknown_axes = set(axes) - set(available)
    if unknown_axes:
        raise ValueError(f"unknown radar benchmarks: {sorted(unknown_axes)}")
    points = list(standardized.get("points", []))
    ids = [point.get("id") for point in points]
    if any(not isinstance(candidate_id, str) or not candidate_id for candidate_id in ids):
        raise ValueError("every candidate must have a non-empty id")
    if len(ids) != len(set(ids)):
        raise ValueError("candidate ids must be unique")
    requested_ids = radar.get("candidate_ids")
    if requested_ids is not None:
        if len(requested_ids) != len(set(requested_ids)):
            raise ValueError("radar candidate_ids contain duplicates")
        unknown = set(requested_ids) - set(ids)
        if unknown:
            raise ValueError(f"unknown selected candidate ids: {sorted(unknown)}")
        points = [point for point in points if point["id"] in set(requested_ids)]
    if not points:
        raise ValueError("no radar candidates selected")
    base, scale = display_parameters(method.get("display_transform", "50 + 10z"))
    candidate_rows = []
    for point in points:
        candidate_id = point["id"]
        model, effort = point.get("model"), point.get("effort")
        if not isinstance(model, str) or not isinstance(effort, str):
            raise ValueError(f"candidate {candidate_id!r} must have model and effort labels")
        benchmark_values = []
        records = point.get("benchmarks", {})
        for benchmark in axes:
            cell = records.get(benchmark, {}).get(metric)
            if not isinstance(cell, dict) or "z" not in cell:
                raise ValueError(f"missing {metric} for {candidate_id!r} / {benchmark!r}")
            z = finite_number(cell["z"], f"z for {candidate_id} / {benchmark}")
            raw = finite_number(cell.get("raw"), f"raw for {candidate_id} / {benchmark}")
            adjusted = finite_number(cell.get("adjusted", raw), f"adjusted for {candidate_id} / {benchmark}")
            benchmark_values.append({
                "benchmark": benchmark,
                "raw": raw,
                "adjusted": adjusted,
                "z": z,
                "display": finite_number(base + scale * z, f"display for {candidate_id} / {benchmark}"),
                "unit": extract_unit(raw_input, method, benchmark, metric),
            })
        candidate_rows.append({"id": candidate_id, "model": model, "effort": effort, "values": benchmark_values})
    display_values = [cell["display"] for candidate in candidate_rows for cell in candidate["values"]]
    low, high = min(display_values), max(display_values)
    span = high - low
    padding = max(span * 0.06, abs(low) * 0.01, 1.0)
    domain = [low - padding, high + padding]
    formula = f"{fmt(base)} + {fmt(scale)} × z"
    if base == 50 and scale == 10:
        display_unit = "deviation-score points"
    elif base == 0 and scale == 1:
        display_unit = "z-score units"
    else:
        display_unit = f"display-score units ({formula})"
    return {
        "schema_version": 1,
        "source_version": standardized.get("version", "unversioned"),
        "metric": metric,
        "metric_label": str(metric_spec.get("label", metric)),
        "display_unit": display_unit,
        "display_formula": formula,
        "display_transform": {"base": base, "scale": scale},
        "radial_domain": domain,
        "axes": axes,
        "candidate_ids": [candidate["id"] for candidate in candidate_rows],
        "candidates": candidate_rows,
    }


def make_text(data: dict[str, Any]) -> dict[str, Any]:
    text = json.loads(json.dumps(DEFAULT_TEXT))
    text["title"] = f"{data['metric_label']} across benchmarks"
    text["subtitle"] = f"Each axis is one benchmark; each line is one model and effort setting ({data['metric_label']})."
    text["interpretation"] = f"A higher display score means a more desirable {data['metric_label']} result. Scores use {data['display_formula']} and are shown in {data['display_unit']}."
    text["display_unit"] = data["display_unit"]
    text["score_formula"] = data["display_formula"]
    text["axes"] = list(data["axes"])
    span = data["radial_domain"][1] - data["radial_domain"][0]
    text["ticks"] = [fmt(data["radial_domain"][0] + span * index / 4) for index in range(5)]
    for candidate in data["candidates"]:
        candidate_id = candidate["id"]
        label = f"{candidate['model']} · {candidate['effort']}"
        text["candidate_labels"][candidate_id] = label
        text["candidate_aria_labels"][candidate_id] = f"Show {label}"
        text["table_rows"].append({
            "candidate": label,
            "values": [
                {"raw": f"{fmt(cell['raw'])} {cell['unit']}", "adjusted": f"{fmt(cell['adjusted'])} {cell['unit']}", "z": fmt(cell["z"]), "display": fmt(cell["display"])}
                for cell in candidate["values"]
            ],
        })
    units = {cell["unit"] for candidate in data["candidates"] for cell in candidate["values"]}
    if "unspecified" in units:
        text["unit_note"] = "Raw values show each declared benchmark unit. ‘unspecified’ means no unit was provided by the source or method."
    return text


def get_pointer(obj: Any, pointer: str) -> str:
    value = obj
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    if not isinstance(value, str):
        raise ValueError(f"text pointer must resolve to a string: {pointer}")
    return value


def bound(pointer: str, text: dict[str, Any], tag: str = "span", attrs: str = "") -> str:
    return f'<{tag} data-text-key="{html.escape(pointer, quote=True)}"{attrs}>{html.escape(get_pointer(text, pointer))}</{tag}>'


def render_svg(data: dict[str, Any], text: dict[str, Any], initial_ids: set[str]) -> str:
    size, center, radius = 900, 450, 280
    low, high = data["radial_domain"]
    count = len(data["axes"])
    angle = lambda index: -math.pi / 2 + 2 * math.pi * index / count
    to_radius = lambda score: radius * (score - low) / (high - low)
    parts = [f'<svg class="radar" viewBox="0 0 {size} {size}" role="img" aria-labelledby="radar-title">', '<title id="radar-title" data-text-key="/title">' + html.escape(get_pointer(text, "/title")) + '</title>']
    for ring, tick in enumerate(text["ticks"]):
        r = to_radius(float(tick))
        points = " ".join(f"{center + r * math.cos(angle(i)):.2f},{center + r * math.sin(angle(i)):.2f}" for i in range(count))
        parts.append(f'<polygon class="grid" points="{points}"/>')
        y = center - r
        parts.append(f'<text class="tick" x="{center + 6}" y="{y - 3:.2f}" data-text-key="/ticks/{ring}">{html.escape(tick)}</text>')
    for i, benchmark in enumerate(data["axes"]):
        a = angle(i)
        x2, y2 = center + radius * math.cos(a), center + radius * math.sin(a)
        label_x, label_y = center + (radius + 32) * math.cos(a), center + (radius + 32) * math.sin(a)
        anchor = "start" if math.cos(a) > .25 else "end" if math.cos(a) < -.25 else "middle"
        parts.append(f'<line class="spoke" x1="{center}" y1="{center}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
        label = get_pointer(text, f"/axes/{i}")
        lines, line = [], ""
        for word in label.split():
            if line and len(line) + 1 + len(word) > 19:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            lines.append(line)
        tspans = "".join(f'<tspan x="{label_x:.2f}" dy="{0 if n == 0 else 14}">{html.escape(part)}{" " if n < len(lines) - 1 else ""}</tspan>' for n, part in enumerate(lines))
        parts.append(f'<text class="axis-label" text-anchor="{anchor}" x="{label_x:.2f}" y="{label_y:.2f}" data-text-key="/axes/{i}">{tspans}</text>')
    dash_patterns = ["none", "7 3", "2 3", "8 2 2 2"]
    for index, candidate in enumerate(data["candidates"]):
        coords = []
        for i, cell in enumerate(candidate["values"]):
            r = to_radius(cell["display"])
            coords.append(f"{center + r * math.cos(angle(i)):.2f},{center + r * math.sin(angle(i)):.2f}")
        dash = dash_patterns[index % len(dash_patterns)]
        dash_attr = "" if dash == "none" else f' stroke-dasharray="{dash}"'
        hidden_attr = "" if candidate["id"] in initial_ids else ' hidden=""'
        parts.append(f'<polygon class="series s{index}" data-candidate="{html.escape(candidate["id"], quote=True)}" points="{" ".join(coords)}"{dash_attr} style="--series-index:{index}"{hidden_attr}/>')
        for i, cell in enumerate(candidate["values"]):
            r = to_radius(cell["display"])
            x, y = center + r * math.cos(angle(i)), center + r * math.sin(angle(i))
            candidate_attr = f'class="vertex s{index}" data-candidate="{html.escape(candidate["id"], quote=True)}"'
            hidden_attr = "" if candidate["id"] in initial_ids else ' hidden=""'
            if index % 3 == 0:
                parts.append(f'<circle {candidate_attr} cx="{x:.2f}" cy="{y:.2f}" r="4"{hidden_attr}/>')
            elif index % 3 == 1:
                parts.append(f'<rect {candidate_attr} x="{x - 3.5:.2f}" y="{y - 3.5:.2f}" width="7" height="7"{hidden_attr}/>')
            else:
                parts.append(f'<polygon {candidate_attr} points="{x:.2f},{y - 4.5:.2f} {x + 4.5:.2f},{y:.2f} {x:.2f},{y + 4.5:.2f} {x - 4.5:.2f},{y:.2f}"{hidden_attr}/>')
    parts.append("</svg>")
    return "".join(parts)


def render_html(data: dict[str, Any], text: dict[str, Any]) -> str:
    if not isinstance(text, dict):
        raise ValueError("reviewed text JSON must be an object")
    minimum_text = {"title", "subtitle", "chart_heading", "series_heading", "table_heading", "candidate_heading", "benchmark_heading", "raw_heading", "adjusted_heading", "display_heading", "z_heading", "interpretation", "unit_note", "radar_note", "fallback_heading", "fallback_note", "unit_unspecified", "display_unit", "score_formula", "axes", "ticks", "candidate_labels", "candidate_aria_labels", "table_rows"}
    if not minimum_text <= text.keys():
        raise ValueError(f"reviewed text is missing keys: {sorted(minimum_text - text.keys())}")
    expected_text = make_text(data)
    for key in ("axes", "ticks", "candidate_labels", "candidate_aria_labels", "table_rows", "display_unit", "score_formula"):
        if text.get(key) != expected_text[key]:
            raise ValueError(f"reviewed text {key} does not match current radar data; rerun --prepare-text and review it")
    initial = initial_selection(data) if len(data["axes"]) >= 3 else set(data["candidate_ids"])
    text_json = json.dumps(text, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title data-text-key="/title">', html.escape(text["title"]), '</title>',
             '<style>body{font:16px/1.5 system-ui,sans-serif;margin:1rem;color:#17212b}main{max-width:1100px;margin:auto}.scroll{overflow-x:auto}.chart-wrap{width:900px;min-width:900px}.radar{display:block;width:900px;min-width:900px;max-width:none;height:auto;margin:auto}.grid{fill:none;stroke:#bbc4cd;stroke-width:1}.spoke{stroke:#d6dce2}.tick{font-size:12px;fill:#59636e}.axis-label{font-size:13px;fill:#17212b}.series{fill:color-mix(in srgb,hsl(calc(var(--series-index)*67 + 17) 68% 43%) 12%,transparent);stroke:hsl(calc(var(--series-index)*67 + 17) 68% 38%);stroke-width:2}.vertex{fill:white;stroke:hsl(calc(var(--series-index)*67 + 17) 68% 38%);stroke-width:2}[hidden]{display:none!important}fieldset{display:flex;flex-wrap:wrap;gap:.5rem 1rem;border:1px solid #c7cdd3}label{cursor:pointer}table{border-collapse:collapse;min-width:100%;white-space:nowrap}th,td{border:1px solid #c7cdd3;padding:.4rem .55rem;text-align:left}.note{max-width:75ch}.fallback{padding:.75rem;border:1px solid #9ca7b1}@media(max-width:600px){body{margin:.5rem}}</style><main>',
             '<h1 data-text-key="/title">', html.escape(text["title"]), '</h1><p data-text-key="/subtitle">', html.escape(text["subtitle"]), '</p>']
    if len(data["axes"]) >= 3:
        parts += ['<section><h2 data-text-key="/chart_heading">', html.escape(text["chart_heading"]), '</h2><p class="note" data-text-key="/interpretation">', html.escape(text["interpretation"]), '</p><p class="note" data-text-key="/radar_note">', html.escape(text["radar_note"]), '</p><div class="scroll"><div class="chart-wrap">', render_svg(data, text, initial), '</div></div>',
                  '<fieldset><legend data-text-key="/series_heading">', html.escape(text["series_heading"]), '</legend>']
        dash_patterns = ["", "7 3", "2 3", "8 2 2 2"]
        for candidate_index, candidate in enumerate(data["candidates"]):
            cid = candidate["id"]
            ptr = "/candidate_labels/" + pointer_part(cid)
            aria_ptr = "/candidate_aria_labels/" + pointer_part(cid)
            checked = " checked" if cid in initial else ""
            aria = html.escape(get_pointer(text, aria_ptr), quote=True)
            parts.append(f'<label><input type="checkbox" data-toggle="{html.escape(cid, quote=True)}" aria-label="{aria}" data-text-attr-aria-label="{aria_ptr}"{checked}>')
            dash = dash_patterns[candidate_index % len(dash_patterns)]
            dash_svg = f' stroke-dasharray="{dash}"' if dash else ""
            parts.append(f'<svg aria-hidden="true" width="30" height="14" viewBox="0 0 30 14" style="vertical-align:middle;color:hsl({candidate_index * 67 + 17} 68% 38%)"><line x1="1" y1="7" x2="29" y2="7" stroke="currentColor" stroke-width="2"{dash_svg}/>')
            if candidate_index % 3 == 0:
                parts.append('<circle cx="15" cy="7" r="3" fill="white" stroke="currentColor" stroke-width="2"/>')
            elif candidate_index % 3 == 1:
                parts.append('<rect x="12" y="4" width="6" height="6" fill="white" stroke="currentColor" stroke-width="2"/>')
            else:
                parts.append('<polygon points="15,3 19,7 15,11 11,7" fill="white" stroke="currentColor" stroke-width="2"/>')
            parts.append('</svg>')
            parts.append(f'<span data-text-key="{ptr}">{html.escape(get_pointer(text, ptr))}</span></label>')
        parts.append('</fieldset></section>')
    else:
        parts += ['<aside class="fallback"><h2 data-text-key="/fallback_heading">', html.escape(text["fallback_heading"]), '</h2><p data-text-key="/fallback_note">', html.escape(text["fallback_note"]), '</p></aside>']
    parts += ['<p class="note" data-text-key="/unit_note">', html.escape(text["unit_note"]), '</p><section><h2 data-text-key="/table_heading">', html.escape(text["table_heading"]), '</h2><div class="scroll"><table><thead><tr><th data-text-key="/candidate_heading">', html.escape(text["candidate_heading"]), '</th>']
    for index, benchmark in enumerate(data["axes"]):
        parts.append(f'<th colspan="4" data-text-key="/axes/{index}">{html.escape(benchmark)}</th>')
    parts.append('</tr><tr><th></th>')
    for _ in data["axes"]:
        for key in ("raw_heading", "adjusted_heading", "z_heading", "display_heading"):
            parts.append(f'<th data-text-key="/{key}">{html.escape(text[key])}</th>')
    parts.append('</tr></thead><tbody>')
    for row_index, row in enumerate(text["table_rows"]):
        if row_index >= len(data["candidates"]):
            break
        cid = data["candidates"][row_index]["id"]
        hidden_attr = "" if cid in initial else ' hidden=""'
        parts.append(f'<tr data-row="{html.escape(cid, quote=True)}"{hidden_attr}><th data-text-key="/table_rows/{row_index}/candidate">{html.escape(row["candidate"])}</th>')
        for axis_index, cells in enumerate(row["values"]):
            for value_key, text_key in (("raw", "raw"), ("adjusted", "adjusted"), ("z", "z"), ("display", "display")):
                ptr = f"/table_rows/{row_index}/values/{axis_index}/{text_key}"
                value = cells[value_key]
                parts.append(f'<td data-text-key="{ptr}">{html.escape(value)}</td>')
        parts.append('</tr>')
    parts += ['</tbody></table></div></section></main>', '<script type="application/json" id="canonical-text">', text_json, '</script>']
    if len(data["axes"]) >= 3:
        parts.append('<script>document.querySelectorAll("[data-toggle]").forEach(box=>box.addEventListener("change",()=>{const id=box.dataset.toggle;document.querySelectorAll("[data-candidate]").forEach(el=>{if(el.dataset.candidate===id){if(box.checked)el.removeAttribute("hidden");else el.setAttribute("hidden","")}});document.querySelectorAll("[data-row]").forEach(row=>{if(row.dataset.row===id){if(box.checked)row.removeAttribute("hidden");else row.setAttribute("hidden","")}})}));</script>')
    return "".join(parts) + "</html>\n"


def initial_selection(data: dict[str, Any]) -> set[str]:
    # Prefer each model's median effort; if it exceeds four models, keep four.
    by_model: dict[str, list[dict[str, Any]]] = {}
    for candidate in data["candidates"]:
        by_model.setdefault(candidate["model"], []).append(candidate)
    chosen = set()
    for model_candidates in by_model.values():
        middle = model_candidates[len(model_candidates) // 2]
        chosen.add(middle["id"])
        if len(chosen) >= 4:
            break
    return chosen or {data["candidates"][0]["id"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standardized", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path, help="optional raw input used only to retrieve declared units")
    parser.add_argument("--output-dir", type=Path, help="new versioned directory; must not already exist")
    parser.add_argument("--prepare-text", type=Path, help="write a draft canonical text JSON and stop before HTML generation")
    parser.add_argument("--text", type=Path, help="reviewed canonical text JSON required for HTML generation")
    args = parser.parse_args()
    standardized, method = read_json(args.standardized), read_json(args.config)
    raw_input = read_json(args.input) if args.input else None
    data = build_data(standardized, method, raw_input)
    draft_text = make_text(data)
    if args.prepare_text:
        args.prepare_text.parent.mkdir(parents=True, exist_ok=True)
        if args.prepare_text.exists():
            raise ValueError(f"refusing to overwrite text file: {args.prepare_text}")
        args.prepare_text.write_text(json.dumps(draft_text, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    if args.output_dir is None or args.text is None:
        parser.error("--output-dir and reviewed --text are required unless --prepare-text is used")
    text = read_json(args.text)
    page = render_html(data, text)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    (output / "radar.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "text.json").write_text(json.dumps(text, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "radar.html").write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"error: {exc}")
