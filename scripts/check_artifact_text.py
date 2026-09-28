#!/usr/bin/env python3
"""Compare canonical text with static HTML and scan artifacts for stale phrases.

Script, style, and template contents are excluded. Runtime-generated text and
template clones need separate browser validation.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
import sys
from pathlib import Path


TEXT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl", ".html", ".js", ".ts", ".css", ".yaml", ".yml"}
TEXT_ATTRIBUTES = {"alt", "title", "aria-label", "placeholder", "value"}
VISIBLE_INPUT_TYPES = {
    "text", "search", "tel", "url", "email", "password", "number",
    "date", "datetime-local", "month", "week", "button", "submit", "reset",
}
IGNORED_CONTENT = {"script", "style", "template"}
VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _json_pointer(value, pointer: str):
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer!r}")
    current = value
    for raw_part in pointer[1:].split("/"):
        if re.search(r"~(?![01])", raw_part):
            raise ValueError(f"invalid JSON pointer escape: {pointer!r}")
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not part.isdigit() or (len(part) > 1 and part.startswith("0")):
                raise ValueError(f"invalid array index in JSON pointer: {pointer!r}")
            try:
                current = current[int(part)]
            except IndexError as exc:
                raise ValueError(f"JSON pointer does not exist: {pointer!r}") from exc
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise ValueError(f"JSON pointer does not exist: {pointer!r}")
    return current


def _normalized_html_text(value: str) -> str:
    # HTML collapses runs of ASCII whitespace in ordinary reader-facing text.
    return " ".join(value.split())


class _VisibleTextParser(HTMLParser):
    """Collect static HTML text and canonical-text JSON bindings."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.bindings: list[dict] = []
        self.unbound: list[str] = []
        self.attribute_bindings: list[tuple[str, str, str]] = []
        self.canonical_chunks: list[str] | None = None
        self.canonical_script_count = 0

    @property
    def ignored(self) -> bool:
        return any(node["tag"] in IGNORED_CONTENT for node in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        parent_ignored = self.ignored
        is_canonical = tag.lower() == "script" and attributes.get("id") == "canonical-text"
        node = {"tag": tag.lower(), "key": attributes.get("data-text-key"), "chunks": [], "canonical": is_canonical}
        if tag.lower() not in VOID_ELEMENTS:
            self.stack.append(node)

        if is_canonical:
            if attributes.get("type", "").lower() != "application/json":
                raise ValueError("canonical-text script must have type=application/json")
            self.canonical_script_count += 1
            if self.canonical_script_count > 1:
                raise ValueError("HTML contains multiple canonical-text scripts")
            self.canonical_chunks = []

        if parent_ignored:
            return
        if node["key"] is not None:
            if any(active["key"] is not None for active in self.stack[:-1]):
                raise ValueError("nested data-text-key elements are ambiguous")
            self.bindings.append(node)

        for attribute in TEXT_ATTRIBUTES:
            if attribute == "value":
                input_type = attributes.get("type", "text").lower() if tag.lower() == "input" else ""
                if input_type not in VISIBLE_INPUT_TYPES:
                    continue
            value = attributes.get(attribute, "")
            pointer_name = f"data-text-attr-{attribute}"
            pointer = attributes.get(pointer_name)
            if value.strip():
                if pointer is None:
                    raise ValueError(f"unbound reader-facing {attribute} attribute on <{tag}>")
                self.attribute_bindings.append((pointer, value, attribute))
            elif pointer is not None:
                raise ValueError(f"{pointer_name} is present but {attribute} is empty on <{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if self.stack and self.stack[-1]["canonical"]:
            self.canonical_chunks.append(data)
        if self.ignored:
            return
        for node in reversed(self.stack):
            if node["key"] is not None:
                node["chunks"].append(data)
                return
        if not data.strip():
            return
        self.unbound.append(_normalized_html_text(data))


def validate_html_text(source: str, canonical) -> object:
    """Check embedded source equality and bind all static HTML text to canonical strings."""
    parser = _VisibleTextParser()
    parser.feed(source)
    parser.close()
    if parser.canonical_script_count:
        if parser.canonical_chunks is None:
            raise ValueError("canonical-text script has no readable body")
        generated = json.loads("".join(parser.canonical_chunks))
        if isinstance(generated, dict) and "text" in generated and generated != canonical:
            generated = generated["text"]
        if generated != canonical:
            raise ValueError("generated text differs from canonical source")
        binding_source = generated
    else:
        # Preserve the established window.D.text embedding format.
        marker = re.search(r"window\.D\s*=\s*", source)
        if not marker:
            raise ValueError("HTML contains neither canonical-text JSON nor window.D.text")
        generated, _ = json.JSONDecoder().raw_decode(source[marker.end():])
        if not isinstance(generated, dict) or "text" not in generated:
            raise ValueError("window.D does not contain a text object")
        binding_source = generated["text"]
        if binding_source != canonical:
            raise ValueError("generated text differs from canonical source")

    if parser.unbound:
        raise ValueError(f"unbound reader-facing HTML text: {parser.unbound[0]!r}")
    for binding in parser.bindings:
        expected = _json_pointer(binding_source, binding["key"])
        if not isinstance(expected, str):
            raise ValueError(f"data-text-key must point to a string: {binding['key']!r}")
        actual = _normalized_html_text("".join(binding["chunks"]))
        if actual != _normalized_html_text(expected):
            raise ValueError(f"HTML text at {binding['key']!r} differs from canonical source")
    for pointer, actual, attribute in parser.attribute_bindings:
        expected = _json_pointer(binding_source, pointer)
        if not isinstance(expected, str) or actual != expected:
            raise ValueError(f"HTML {attribute} attribute at {pointer!r} differs from canonical source")
    return generated


def load_generated(path: Path, canonical=None):
    if path.suffix.lower() != ".html":
        return load_json(path)
    source = path.read_text(encoding="utf-8")
    if canonical is None:
        parser = _VisibleTextParser()
        parser.feed(source)
        parser.close()
        if parser.canonical_chunks is not None:
            return json.loads("".join(parser.canonical_chunks))
        marker = re.search(r"window\.D\s*=\s*", source)
        if marker:
            payload, _ = json.JSONDecoder().raw_decode(source[marker.end():])
            if not isinstance(payload, dict) or "text" not in payload:
                raise ValueError("window.D does not contain a text object")
            return payload["text"]
        raise ValueError("HTML contains neither canonical-text JSON nor window.D.text")
    return validate_html_text(source, canonical)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True, help="artifact directory to scan for stale phrases")
    parser.add_argument("--forbidden", type=Path, required=True, help="JSON file containing a list of forbidden/stale phrases; use [] when none apply")
    parser.add_argument("--integrity-manifest", type=Path, required=True, help="JSON manifest containing the generated artifact sha256")
    args = parser.parse_args()
    try:
        canonical = load_json(args.canonical)
        generated = load_generated(args.generated, canonical if args.generated.suffix.lower() == ".html" else None)
        if generated != canonical and isinstance(generated, dict) and "text" in generated:
            generated = generated["text"]
        if generated != canonical:
            print("FAIL: generated text differs from canonical source")
            return 1
        manifest = load_json(args.integrity_manifest)
        expected_hash = manifest.get("sha256") if isinstance(manifest, dict) else None
        actual_hash = hashlib.sha256(args.generated.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            print("FAIL: generated artifact hash differs from integrity manifest")
            return 1
        if manifest.get("bytes") is not None and int(manifest["bytes"]) != args.generated.stat().st_size:
            print("FAIL: generated artifact byte count differs from integrity manifest")
            return 1
        if manifest.get("artifact") and Path(manifest["artifact"]).name != args.generated.name:
            print("FAIL: integrity manifest names a different generated artifact")
            return 1
        forbidden = load_json(args.forbidden)
        if not isinstance(forbidden, list) or not all(isinstance(item, str) and item for item in forbidden):
            raise ValueError("forbidden must be a JSON string list")
        if not args.root.is_dir():
            raise ValueError(f"root is not a directory: {args.root}")
        review_inputs = {path.resolve() for path in (args.canonical, args.forbidden, args.integrity_manifest)}
        for path in args.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if path.resolve() in review_inputs:
                continue
            text = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                if phrase in text:
                    print(f"FAIL: stale phrase {phrase!r} in {path}")
                    return 1
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print("PASS: canonical text, visible HTML bindings, and stale-phrase contract validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
