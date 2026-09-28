#!/usr/bin/env python3
"""Build directed fixed-grid adjacency edges from model/effort order."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = read_json(args.input)
    config = read_json(args.config)
    points = list(source.get("points", []))
    models = {model: index for index, model in enumerate(config["model_order"])}
    efforts = {effort: index for index, effort in enumerate(config["effort_order"])}
    boundary_pairs = {tuple(pair) for pair in config.get("boundary_model_pairs", [])}
    existing = {(point["model"], point["effort"]): point["id"] for point in points}
    edges = []
    for (model, effort), source_id in sorted(existing.items(), key=lambda item: (models[item[0][0]], efforts[item[0][1]])):
        effort_index = efforts[effort]
        if effort_index + 1 < len(config["effort_order"]):
            target_id = existing.get((model, config["effort_order"][effort_index + 1]))
            if target_id:
                edges.append({"from": source_id, "to": target_id, "type": "effort", "boundary": False})
        model_index = models[model]
        if model_index + 1 < len(config["model_order"]):
            target_model = config["model_order"][model_index + 1]
            target_id = existing.get((target_model, effort))
            if target_id:
                edges.append({"from": source_id, "to": target_id, "type": "model", "boundary": (model, target_model) in boundary_pairs})
    args.output.write_text(json.dumps({"edges": edges}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"edge_count": len(edges), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
