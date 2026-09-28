#!/usr/bin/env python3
"""Filter fixed-grid edges to the configured MDS fit without spatial inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid-edges", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    grid_edges = read_json(args.grid_edges).get("edges", [])
    config = read_json(args.config)
    mds_config = config.get("mds", {})
    fit_ids = set(mds_config.get("fit_ids", []))
    include_boundary = bool(mds_config.get("include_boundary_edges", False))
    mds_edges = [
        edge for edge in grid_edges
        if edge.get("from") in fit_ids
        and edge.get("to") in fit_ids
        and (include_boundary or not edge.get("boundary", False))
    ]
    args.output.write_text(json.dumps({"edges": mds_edges, "source": "fixed_grid_adjacency_filter"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"edge_count": len(mds_edges), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
