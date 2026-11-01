"""Build gold localization labels (file / symbol / graph node) for every task.

Usage: python scripts/build_labels.py DATA_DIR  ->  results/gold_labels.jsonl, results/index/*.json
DATA_DIR holds tasks.jsonl, graphs/, and repos/<name> (git clones of the four upstream repos).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wtfl.patch import parse_patch  # noqa: E402
from wtfl.repo_index import build_index, enclosing, load_graph  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def short(repo: str) -> str:
    return repo.split("/")[1]


def main(data: Path):
    out_dir = ROOT / "results" / "index"
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in open(data / "tasks.jsonl")]
    labels = []
    for t in tasks:
        key = f"{short(t['repo'])}_{t['base_commit']}"
        gpath = data / "graphs" / f"{key}.json"
        g = load_graph(str(gpath))
        names = {n["id"] for n in g["nodes"]}
        cache = out_dir / f"{key}.json"
        if cache.exists():
            idx = json.loads(cache.read_text())
        else:
            idx = build_index(data / "repos" / short(t["repo"]), t["base_commit"], names)
            cache.write_text(json.dumps(idx))
        files = parse_patch(t["patch"])
        gold_nodes, gold_files, rows_out = [], [], []
        for f in files:
            sym = []
            if not f["is_new"] and f["path"].endswith(".py"):
                rows = idx["file_defs"].get(f["path"], [])
                for ln in f["lines"]:
                    enc = enclosing(rows, ln)
                    sym.append({"line": ln, "node": enc[0] if enc else None,
                                "qualname": enc[1] if enc else None})
            nodes = sorted({s["node"] for s in sym if s["node"]})
            gold_nodes += [n for n in nodes if n not in gold_nodes]
            if not f["is_new"]:
                gold_files.append(f["path"])
            rows_out.append({**f, "symbols": sym, "nodes": nodes})
        labels.append({
            "instance_id": t["instance_id"], "repo": t["repo"], "graph_key": key,
            "n_graph_nodes": len(names), "n_graph_edges": len(g["edges"]),
            "files": rows_out, "gold_files": gold_files, "gold_nodes": gold_nodes,
            "n_py_files": len(idx["py_files"]), "n_mapped_nodes": len(idx["node2loc"]),
        })
        print(t["instance_id"], len(gold_files), len(gold_nodes), flush=True)
    with open(ROOT / "results" / "gold_labels.jsonl", "w") as fh:
        for l in labels:
            fh.write(json.dumps(l) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
