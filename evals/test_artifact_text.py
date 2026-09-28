"""Regression tests for canonical text bindings in generated HTML."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_artifact_text import validate_html_text  # noqa: E402


CANONICAL = {
    "title": "Trade-off summary",
    "label": "Low & cost",
    "svg": "Axis title",
    "aria": "Open details",
    "input": "Find candidate",
}


def html_with(text: str = "Low <strong>&amp;</strong> <i>cost</i>", extra: str = "") -> str:
    source = json.dumps(CANONICAL, ensure_ascii=False)
    return f'''<!doctype html><html><head>
<script id="canonical-text" type="application/json">{source}</script>
</head><body><h1 data-text-key="/title">Trade-off summary</h1>
<p data-text-key="/label">{text}</p>
<svg><text data-text-key="/svg">Axis title</text></svg>
<button aria-label="Open details" data-text-attr-aria-label="/aria"></button>{extra}
<input type="checkbox" value="machine-value"><input type="text" value="Find candidate" data-text-attr-value="/input">
</body></html>'''


class ArtifactTextTests(unittest.TestCase):
    def test_valid_html_accepts_attribute_order_entities_inline_markup_and_svg(self):
        source = html_with()
        self.assertEqual(validate_html_text(source, CANONICAL), CANONICAL)

    def test_changed_bound_visible_text_fails(self):
        with self.assertRaisesRegex(ValueError, "differs from canonical"):
            validate_html_text(html_with(text="Low <strong>&amp;</strong> <i>risk</i>"), CANONICAL)

    def test_machine_value_attributes_are_ignored_but_visible_input_values_are_bound(self):
        source = html_with()
        self.assertEqual(validate_html_text(source, CANONICAL), CANONICAL)
        with self.assertRaisesRegex(ValueError, "unbound reader-facing value"):
            validate_html_text(source.replace('value="Find candidate" data-text-attr-value="/input"', 'value="Unreviewed input"'), CANONICAL)

    def test_unbound_h1_fails_even_when_canonical_json_is_correct(self):
        source = html_with(extra="<h1>Unreviewed headline</h1>")
        with self.assertRaisesRegex(ValueError, "unbound reader-facing HTML text"):
            validate_html_text(source, CANONICAL)

    def test_unbound_reader_facing_attribute_fails(self):
        source = html_with(extra='<img alt="Unreviewed description">')
        with self.assertRaisesRegex(ValueError, "unbound reader-facing alt"):
            validate_html_text(source, CANONICAL)

    def test_json_pointer_resolves_escaped_keys_and_array_positions(self):
        canonical = {"a/b": ["first", {"~key": "target"}]}
        source = json.dumps(canonical)
        html = (
            f'<script type="application/json" id="canonical-text">{source}</script>'
            '<p data-text-key="/a~1b/1/~0key">target</p>'
        )
        self.assertEqual(validate_html_text(html, canonical), canonical)

    def test_hash_manifest_detects_post_manifest_html_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            generated = directory / "artifact.html"
            generated.write_text(html_with(), encoding="utf-8")
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({
                "artifact": generated.name,
                "sha256": hashlib.sha256(generated.read_bytes()).hexdigest(),
                "bytes": generated.stat().st_size,
            }), encoding="utf-8")
            generated.write_text(generated.read_text(encoding="utf-8") + "<!-- late edit -->", encoding="utf-8")
            canonical = directory / "canonical.json"
            canonical.write_text(json.dumps(CANONICAL), encoding="utf-8")
            forbidden = directory / "forbidden.json"
            forbidden.write_text("[]", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "check_artifact_text.py"),
                    "--canonical", str(canonical),
                    "--generated", str(generated),
                    "--root", str(directory),
                    "--forbidden", str(forbidden),
                    "--integrity-manifest", str(manifest),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("artifact hash differs", result.stdout)


if __name__ == "__main__":
    unittest.main()
