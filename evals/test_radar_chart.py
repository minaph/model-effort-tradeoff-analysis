"""Focused, independent checks for the radar chart builder."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_radar_chart.py"
SPEC = importlib.util.spec_from_file_location("build_radar_chart", SCRIPT)
radar = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(radar)


def fixture(axes=("A", "B", "C")):
    candidates = [
        {"id": "Model/One|low", "model": "Model/One", "effort": "low", "benchmarks": {}},
        {"id": "Model/One|high", "model": "Model/One", "effort": "high", "benchmarks": {}},
        {"id": "Model~Two|low", "model": "Model~Two", "effort": "low", "benchmarks": {}},
    ]
    z_by_id = {
        candidates[0]["id"]: (-10.0, 0.0, 2.0),
        candidates[1]["id"]: (0.5, -2.0, 1.0),
        candidates[2]["id"]: (3.0, 1.0, -0.5),
    }
    for candidate in candidates:
        for index, axis in enumerate(axes):
            z = z_by_id[candidate["id"]][index]
            candidate["benchmarks"].setdefault(axis, {})["performance"] = {
                "raw": 100 + index * 10 + z,
                "adjusted": 100 + index * 10 + z,
                "z": z,
            }
    standardized = {"version": "fixture", "selected_benchmarks": list(axes), "excluded_benchmarks": ["Composite"], "points": candidates}
    config = {
        "selected_benchmarks": list(axes),
        "excluded_benchmarks": ["Composite"],
        "metrics": {"performance": {"field": "score", "unit": "%", "label": "Accuracy"}},
        "display_transform": "50 + 10z",
        "radar": {"metric": "performance"},
    }
    return standardized, config


class RadarChartTests(unittest.TestCase):
    def test_transforms_scores_and_keeps_negative_extreme_inside_domain(self):
        standardized, config = fixture()
        data = radar.build_data(standardized, config)
        # Independent expectations use z directly and the declared affine transform.
        first = data["candidates"][0]["values"]
        self.assertEqual([cell["display"] for cell in first], [-50.0, 50.0, 70.0])
        scores = [cell["display"] for candidate in data["candidates"] for cell in candidate["values"]]
        self.assertLess(data["radial_domain"][0], min(scores))
        self.assertGreater(data["radial_domain"][1], max(scores))
        self.assertLess(min(scores), 0)
        self.assertEqual(data["axes"], ["A", "B", "C"])
        self.assertEqual(first[0]["unit"], "%")
        self.assertEqual(data["display_unit"], "deviation-score points")

    def test_rendered_chart_and_text_share_complete_candidate_domain(self):
        standardized, config = fixture()
        data = radar.build_data(standardized, config)
        text = radar.make_text(data)
        page = radar.render_html(data, text)
        self.assertEqual(len(data["candidates"]), 3)
        self.assertEqual(page.count('class="series '), 3)
        self.assertIn('id="canonical-text"', page)
        self.assertIn('data-text-attr-aria-label="/candidate_aria_labels/Model~1One|low"', page)
        self.assertIn("Polygon area is not a ranking", text["radar_note"])
        # The initial checkbox state only hides series in the browser; no selected-domain recomputation exists.
        self.assertIn("radial_domain", data)
        self.assertIn("const id=box.dataset.toggle", page)
        self.assertGreater(page.count('hidden=""'), 0)
        self.assertIn('colspan="4"', page)
        self.assertIn('data-candidate="Model/One|low" points="', page)
        self.assertIn('.chart-wrap{width:900px;min-width:900px}', page)
        self.assertIn('.tick{font-size:12px', page)
        self.assertIn('.axis-label{font-size:13px', page)
        self.assertIn('data-row="Model/One|low" hidden=""', page)
        self.assertIn('data-row="Model/One|high"', page)
        stale = dict(text)
        stale["table_rows"] = [dict(text["table_rows"][0])]
        with self.assertRaisesRegex(ValueError, "table_rows does not match"):
            radar.render_html(data, stale)
        stale = dict(text)
        stale["ticks"] = list(text["ticks"])
        stale["ticks"][0] = "0"
        with self.assertRaisesRegex(ValueError, "ticks does not match"):
            radar.render_html(data, stale)

    def test_two_benchmarks_use_explicit_table_only_fallback(self):
        standardized, config = fixture(("A", "B"))
        data = radar.build_data(standardized, config)
        text = radar.make_text(data)
        page = radar.render_html(data, text)
        self.assertIn("Radar view unavailable", page)
        self.assertNotIn('class="radar"', page)
        self.assertIn("Values by candidate and benchmark", page)
        self.assertEqual(page.count('data-row="'), 3)
        self.assertNotIn('data-row="Model/One|low" hidden=""', page)

    def test_raw_input_units_are_used_or_left_unspecified(self):
        standardized, config = fixture()
        source = {"points": [{"raw": {axis: {"score": 1, "unit": "tasks"} for axis in ("A", "B", "C")}}]}
        with self.assertRaisesRegex(ValueError, "units conflict"):
            radar.build_data(standardized, config, source)
        config["metrics"]["performance"]["unit"] = "tasks"
        data = radar.build_data(standardized, config, source)
        self.assertEqual(data["candidates"][0]["values"][0]["unit"], "tasks")
        config["metrics"]["performance"].pop("unit")
        data = radar.build_data(standardized, config, source)
        self.assertEqual(data["candidates"][0]["values"][0]["unit"], "tasks")
        config = {"selected_benchmarks": ["A", "B", "C"], "excluded_benchmarks": ["Composite"], "metrics": {"performance": {"field": "score"}}, "display_transform": "50 + 10z"}
        data = radar.build_data(standardized, config)
        self.assertEqual(data["candidates"][0]["values"][0]["unit"], "unspecified")
        config["display_transform"] = "z"
        data = radar.build_data(standardized, config)
        self.assertEqual(data["display_unit"], "z-score units")

    def test_custom_affine_transform_and_long_axis_labels(self):
        long_axis = "Artificial Analysis Intelligence Benchmark"
        standardized, config = fixture((long_axis, "Task B", "Task C"))
        config["display_transform"] = {"base": -3, "scale": 2}
        data = radar.build_data(standardized, config)
        first = data["candidates"][0]["values"][0]
        self.assertEqual(first["display"], -23)
        self.assertEqual(data["display_unit"], "display-score units (-3 + 2 × z)")
        page = radar.render_html(data, radar.make_text(data))
        self.assertIn('data-text-key="/axes/0"><tspan', page)
        self.assertIn("Artificial Analysis ", page)
        self.assertIn("width:900px;min-width:900px", page)

    def test_rejects_composites_unknown_ids_duplicates_missing_and_nonfinite_values(self):
        standardized, config = fixture()
        config["radar"]["benchmarks"] = ["Composite", "A", "B"]
        with self.assertRaisesRegex(ValueError, "excluded/composite"):
            radar.build_data(standardized, config)
        config["radar"]["benchmarks"] = ["A", "A", "B"]
        with self.assertRaisesRegex(ValueError, "duplicates"):
            radar.build_data(standardized, config)
        config["radar"]["benchmarks"] = ["A", "B", "C"]
        config["radar"]["candidate_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown selected"):
            radar.build_data(standardized, config)
        del config["radar"]["candidate_ids"]
        standardized["points"][0]["benchmarks"]["B"]["performance"]["z"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            radar.build_data(standardized, config)
        standardized, config = fixture()
        del standardized["points"][0]["benchmarks"]["B"]
        with self.assertRaisesRegex(ValueError, "missing performance"):
            radar.build_data(standardized, config)


if __name__ == "__main__":
    unittest.main()
