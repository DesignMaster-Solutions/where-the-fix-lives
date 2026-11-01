"""RQ1 + RQ2: anchor/graph statistics and ranker evaluation for every task.

Usage: python scripts/run_rankers.py DATA_DIR  ->  results/per_task.jsonl, results/rankings/*.json
"""
import json
import sys
from pathlib import Path

import networkx as nx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wtfl.anchors import file_anchors, mentioned_identifiers, symbol_anchors  # noqa: E402
from wtfl.rankers import RepoView, is_test_node, rank_all, rrf  # noqa: E402

# hybrid weight grid (anchor+bm25, bm25, ppr, emb); the paper's hybrid uses (2, 1, 1, 0.5), fixed before any result
WEIGHTS = {"w1111": (1, 1, 1, 1), "w2100": (2, 1, 0, 0), "w2110": (2, 1, 1, 0), "w2101": (2, 1, 0, 1), "w4110": (4, 1, 1, 0.5)}

ROOT = Path(__file__).resolve().parents[1]
KS = (1, 3, 5, 10, 20, 50)


def first_hit(ranking, gold) -> int | None:
    for i, n in enumerate(ranking):
        if n in gold:
            return i + 1
    return None


def file_ranking(node_ranking, node2file) -> list:
    out, seen = [], set()
    for n in node_ranking:
        f = node2file.get(n)
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def main(data: Path):
    tasks = {json.loads(l)["instance_id"]: json.loads(l) for l in open(data / "tasks.jsonl")}
    labels = [json.loads(l) for l in open(ROOT / "results" / "gold_labels.jsonl")]
    (ROOT / "results" / "rankings").mkdir(exist_ok=True)
    rows = []
    for lab in labels:
        t = tasks[lab["instance_id"]]
        key = lab["graph_key"]
        graph = json.loads((data / "graphs" / f"{key}.json").read_text())
        z = np.load(data / "embeddings" / f"{key}.npz")
        emb = {k: z[k] for k in z.files}
        idx = json.loads((ROOT / "results" / "index" / f"{key}.json").read_text())
        node2file = {n: loc[0] for n, loc in idx["node2loc"].items()}
        view = RepoView(graph, emb)
        issue = t["problem_statement"] + ("\n" + t["hints_text"] if t["hints_text"] else "")

        fa = file_anchors(issue, idx["py_files"])
        sa_names = symbol_anchors(issue, view.nodes)
        anchors = sa_names | {n for n in view.nodes if node2file.get(n) in fa}
        gold = {n for n in lab["gold_nodes"] if not is_test_node(n)}
        gold_files = {f for f in lab["gold_files"] if f.endswith(".py")}
        ranks = rank_all(view, issue, anchors)

        # graph distance from nearest anchor to nearest gold node (undirected calls graph)
        dist, hood = None, None
        if anchors and gold:
            src = [a for a in anchors if a in view.g]
            if src:
                lengths = nx.multi_source_dijkstra_path_length(view.g, set(src), cutoff=6)
                d = [lengths[g] for g in gold if g in lengths]
                dist = min(d) if d else float("inf")
                # share of candidate nodes within k hops of an anchor: how much a k-hop prior narrows the search
                hood = [sum(1 for v in lengths.values() if v <= k) / len(view.nodes) for k in range(4)]
        row = {
            "instance_id": lab["instance_id"], "repo": lab["repo"],
            "n_nodes": len(view.nodes), "n_edges": view.g.number_of_edges(),
            "n_gold_nodes": len(gold), "n_gold_files": len(lab["gold_files"]),
            "n_gold_py_files": len(gold_files),
            "only_new_files": all(f["is_new"] for f in lab["files"]),
            "has_new_file": any(f["is_new"] for f in lab["files"]),
            "touches_non_py": any(not f["path"].endswith(".py") for f in lab["files"]),
            "module_level_only": bool(gold_files) and not gold,
            "n_ids": len(mentioned_identifiers(issue)),
            "file_anchor": bool(fa), "file_anchor_hits_gold": bool(fa & gold_files),
            "n_anchors": len(anchors), "anchor_hits_gold": bool(anchors & gold),
            "anchor_gold_dist": dist, "anchor_hood_frac": hood,
            "gold_isolated": bool(gold) and all(view.g.degree(g) == 0 for g in gold if g in view.g),
            "gold_has_emb": bool(gold) and any(g in view.emb_row for g in gold),
            "issue_chars": len(issue),
        }
        for w, wt in WEIGHTS.items():
            r = rrf([ranks["anchor+bm25"], ranks["bm25"], ranks["ppr"], ranks["emb_knn"]], weights=list(wt))
            row[f"node_rank_hyb_{w}"] = first_hit(r, gold) if gold else None
        for name, r in ranks.items():
            row[f"node_rank_{name}"] = first_hit(r, gold) if gold else None
            fr = file_ranking(r, node2file)
            row[f"file_rank_{name}"] = first_hit(fr, gold_files) if gold_files else None
        rows.append(row)
        (ROOT / "results" / "rankings" / f"{lab['instance_id']}.json").write_text(json.dumps(
            {k: v[:100] for k, v in ranks.items() if k != "random"}))
        print(lab["instance_id"], row["anchor_hits_gold"], row["node_rank_bm25"], row["node_rank_hybrid"], flush=True)
    with open(ROOT / "results" / "per_task.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
