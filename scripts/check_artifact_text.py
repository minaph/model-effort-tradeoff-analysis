#!/usr/bin/env python3
"""Compare canonical text JSON and scan generated artifacts for stale phrases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


TEXT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl", ".html", ".js", ".ts", ".css", ".yaml", ".yml"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_generated(path: Path):
    if path.suffix.lower() != ".html":
        return load_json(path)
    source = path.read_text(encoding="utf-8")
    script_match = re.search(r'<script[^>]*type=["\']application/json["\'][^>]*id=["\']canonical-text["\'][^>]*>(.*?)</script>', source, re.DOTALL | re.IGNORECASE)
    if script_match:
        return json.loads(script_match.group(1))
    marker = re.search(r"window\.D\s*=\s*", source)
    if marker:
        decoder = json.JSONDecoder()
        payload, _ = decoder.raw_decode(source[marker.end():])
        if not isinstance(payload, dict) or "text" not in payload:
            raise ValueError("window.D does not contain a text object")
        return payload["text"]
    raise ValueError("HTML contains neither canonical-text JSON nor window.D.text")


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
        generated = load_generated(args.generated)
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
        for path in args.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            text = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                if phrase in text:
                    print(f"FAIL: stale phrase {phrase!r} in {path}")
                    return 1
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print("PASS: canonical text and stale-phrase contract validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
