"""Training-free localization rankers over the provided code graph and node embeddings.

Every ranker returns a list of graph node ids, best first. Test-module nodes are excluded
(the gold patches in this benchmark never edit tests; test edits live in test_patch).
"""
import networkx as nx
import numpy as np
from rank_bm25 import BM25Okapi

from .anchors import tokens


def is_test_node(n: str) -> bool:
    return any(p == "tests" or p == "test" or p.startswith("test_") for p in n.split(".")[:-1]) \
        or n.split(".")[0] in ("tests", "test")


class RepoView:
    """Per-commit view: candidate nodes, BM25 index, undirected call graph, embedding matrix."""

    def __init__(self, graph: dict, emb: dict):
        self.nodes = [n["id"] for n in graph["nodes"] if not is_test_node(n["id"])]
        keep = set(self.nodes)
        text = {n["id"]: n.get("text") or "" for n in graph["nodes"]}
        docs = [tokens(n.replace(".", " ")) * 3 + tokens(text[n]) for n in self.nodes]
        self.bm25 = BM25Okapi(docs)
        g = nx.Graph()
        g.add_nodes_from(self.nodes)
        g.add_edges_from((e["source"], e["target"]) for e in graph["edges"]
                         if e["source"] in keep and e["target"] in keep and e["source"] != e["target"])
        self.g = g
        ids = [n for n in self.nodes if n in emb]
        self.emb_ids = ids
        m = np.stack([emb[n] for n in ids]).astype(np.float32) if ids else np.zeros((0, 1), np.float32)
        self.emb = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
        self.emb_row = {n: i for i, n in enumerate(ids)}

    # --- individual scorers: dict node -> score -----------------------------------------
    def bm25_scores(self, query: str) -> dict:
        s = self.bm25.get_scores(tokens(query))
        return dict(zip(self.nodes, s))

    def emb_scores(self, seeds) -> dict:
        rows = [self.emb_row[s] for s in seeds if s in self.emb_row]
        if not rows:
            return {}
        q = self.emb[rows].mean(0)
        q /= np.linalg.norm(q) + 1e-9
        return dict(zip(self.emb_ids, self.emb @ q))

    def ppr_scores(self, seeds, alpha: float = 0.85) -> dict:
        seeds = {s: w for s, w in seeds.items() if s in self.g}
        if not seeds or self.g.number_of_edges() == 0:
            return {}
        return nx.pagerank(self.g, alpha=alpha, personalization=seeds, max_iter=200, tol=1e-8)


def order(scores: dict, fallback=()) -> list:
    ranked = [n for n, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
    seen = set(ranked)
    return ranked + [n for n in fallback if n not in seen]


def rrf(rankings, weights=None, k: int = 60) -> list:
    """Reciprocal rank fusion of several rankings."""
    weights = weights or [1.0] * len(rankings)
    acc = {}
    for r, w in zip(rankings, weights):
        for i, n in enumerate(r):
            acc[n] = acc.get(n, 0.0) + w / (k + i + 1)
    return order(acc)


def rank_all(view: RepoView, issue: str, anchors: set, n_prf: int = 5) -> dict:
    """All rankers for one task. Anchors = nodes named by the issue (may be empty).

    Without anchors, graph/embedding rankers are seeded by the top BM25 nodes
    (pseudo-relevance feedback), so every ranker returns a full ranking.
    """
    bm = order(view.bm25_scores(issue))
    anchors = [a for a in anchors if a in set(view.nodes)]
    anchor_ranked = [n for n in bm if n in set(anchors)]
    seeds = anchor_ranked[:20] if anchor_ranked else bm[:n_prf]
    ppr = order(view.ppr_scores({s: 1.0 for s in seeds}), bm)
    emb = order(view.emb_scores(seeds), bm)
    out = {
        "random": list(np.random.default_rng(0).permutation(view.nodes)),
        "bm25": bm,
        "anchor+bm25": anchor_ranked + [n for n in bm if n not in set(anchor_ranked)],
        "emb_knn": emb,
        "ppr": ppr,
    }
    out["hybrid"] = rrf([out["anchor+bm25"], bm, ppr, emb], weights=[2.0, 1.0, 1.0, 0.5])
    return out
