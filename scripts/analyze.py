"""Tables and figures from results/per_task.jsonl (and results/llm_*.jsonl when present).

Usage: python scripts/analyze.py  ->  results/tables.md, results/summary.json, figures/*.png
"""
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RANKERS = ["random", "bm25", "emb_knn", "ppr", "anchor+bm25", "hybrid"]
KS = (1, 5, 10, 20)
B = 2000


def boot_ci(x, rng):
    x = np.asarray(x, float)
    if len(x) == 0:
        return (float("nan"),) * 3
    s = rng.choice(x, (B, len(x))).mean(1)
    return float(x.mean()), float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))


def paired_diff(a, b, rng):
    d = np.asarray(a, float) - np.asarray(b, float)
    s = rng.choice(d, (B, len(d))).mean(1)
    return float(d.mean()), float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5)), float((s <= 0).mean())


def hit(r, k):
    return 1.0 if r is not None and r <= k else 0.0


def main():
    rng = np.random.default_rng(0)
    rows = [json.loads(l) for l in open(ROOT / "results" / "per_task.jsonl")]
    S, md = {}, []
    n = len(rows)
    node_set = [r for r in rows if r["n_gold_nodes"] > 0]
    file_set = [r for r in rows if r["n_gold_py_files"] > 0]

    # ---- RQ1: structure ----
    def frac(pred, pop):
        v = [1.0 if pred(r) else 0.0 for r in pop]
        return boot_ci(v, rng) + (int(sum(v)), len(v))
    rq1 = {
        "only_new_files": frac(lambda r: r["only_new_files"], rows),
        "has_new_file": frac(lambda r: r["has_new_file"], rows),
        "single_file": frac(lambda r: r["n_gold_files"] + 0 == 1 and not r["has_new_file"], rows),
        "module_level_only": frac(lambda r: r["module_level_only"], file_set),
        "file_anchor_any": frac(lambda r: r["file_anchor"], file_set),
        "file_anchor_hits_gold": frac(lambda r: r["file_anchor_hits_gold"], file_set),
        "symbol_anchor_any": frac(lambda r: r["n_anchors"] > 0, node_set),
        "anchor_hits_gold_node": frac(lambda r: r["anchor_hits_gold"], node_set),
        "gold_isolated_in_call_graph": frac(lambda r: r["gold_isolated"], node_set),
        "gold_has_embedding": frac(lambda r: r["gold_has_emb"], node_set),
    }
    with_anchor = [r for r in node_set if r["n_anchors"] > 0]
    dists = [r["anchor_gold_dist"] for r in with_anchor]
    hop = {}
    for k in (0, 1, 2, 3):
        hop[k] = frac(lambda r, k=k: r["anchor_gold_dist"] is not None and r["anchor_gold_dist"] <= k, with_anchor)
    rq1["anchor_gold_hops"] = hop
    hoods = np.array([r["anchor_hood_frac"] for r in with_anchor if r.get("anchor_hood_frac")])
    S["anchor_hood_median_frac"] = np.median(hoods, 0).tolist() if len(hoods) else None
    S["rq1"] = rq1
    S["n_tasks"], S["n_node_eval"], S["n_file_eval"] = n, len(node_set), len(file_set)
    S["median_candidates"] = float(np.median([r["n_nodes"] for r in node_set]))
    S["median_edges"] = float(np.median([r["n_edges"] for r in node_set]))

    md.append(f"# Results\n\nTasks: {n}; with a gold graph node (function-level eval): {len(node_set)}; "
              f"with a gold existing .py file (file-level eval): {len(file_set)}.\n")
    if S.get("anchor_hood_median_frac"):
        md.append("Median share of candidate nodes within k=0..3 call-graph hops of an anchor: "
                  + ", ".join(f"{v:.3f}" for v in S["anchor_hood_median_frac"]) + "\n")
    md.append("## RQ1 structure (mean [95% bootstrap CI], count/total)\n")
    md.append("| quantity | value |\n|---|---|")
    for k, v in rq1.items():
        if k == "anchor_gold_hops":
            for h, vv in v.items():
                md.append(f"| gold within {h} hops of an anchor (tasks with anchors) | {vv[0]:.2f} [{vv[1]:.2f}, {vv[2]:.2f}] {vv[3]}/{vv[4]} |")
        else:
            md.append(f"| {k} | {v[0]:.2f} [{v[1]:.2f}, {v[2]:.2f}] {v[3]}/{v[4]} |")

    # ---- RQ2: rankers ----
    S["rq2"] = {}
    for level, pop in (("node", node_set), ("file", file_set)):
        md.append(f"\n## RQ2 {level}-level hit@k (mean [95% CI]), n={len(pop)}\n")
        md.append("| ranker | " + " | ".join(f"@{k}" for k in KS) + " | MRR |\n|---|" + "---|" * (len(KS) + 1))
        for rk in RANKERS:
            ranks = [r[f"{level}_rank_{rk}"] for r in pop]
            cells, entry = [], {}
            for k in KS:
                m, lo, hi = boot_ci([hit(x, k) for x in ranks], rng)
                cells.append(f"{m:.3f} [{lo:.2f}, {hi:.2f}]")
                entry[f"hit@{k}"] = (m, lo, hi)
            mrr = boot_ci([1 / x if x else 0 for x in ranks], rng)
            entry["mrr"] = mrr
            cells.append(f"{mrr[0]:.3f}")
            S["rq2"][f"{level}/{rk}"] = entry
            md.append(f"| {rk} | " + " | ".join(cells) + " |")
        for a, b in (("hybrid", "bm25"), ("ppr", "bm25"), ("emb_knn", "bm25"), ("hybrid", "anchor+bm25")):
            for k in (1, 10):
                d = paired_diff([hit(r[f"{level}_rank_{a}"], k) for r in pop],
                                [hit(r[f"{level}_rank_{b}"], k) for r in pop], rng)
                S["rq2"][f"{level}/diff/{a}-{b}@{k}"] = d
                md.append(f"\npaired {a} - {b} hit@{k}: {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}], P(diff<=0)={d[3]:.3f}")

    # anchored vs unanchored split (anchor = the issue names some code; hit = it names the gold)
    SUB = ("bm25", "anchor+bm25", "ppr", "emb_knn", "hybrid")
    splits = (("issue names a gold symbol/file", [r for r in node_set if r["anchor_hits_gold"]]),
              ("issue names code, but not the gold", [r for r in node_set if r["n_anchors"] and not r["anchor_hits_gold"]]),
              ("issue names no code", [r for r in node_set if not r["n_anchors"]]))
    for k in (1, 10):
        md.append(f"\n## RQ2 node hit@{k} by anchoring\n\n| subset | n | " + " | ".join(SUB) + " |\n|---|---|" + "---|" * len(SUB))
        for name, pop in splits:
            vals = [boot_ci([hit(r[f"node_rank_{rk}"], k) for r in pop], rng) for rk in SUB]
            S["rq2"][f"split@{k}/{name}"] = {"n": len(pop), **dict(zip(SUB, vals))}
            md.append(f"| {name} | {len(pop)} | " + " | ".join(f"{v[0]:.3f} [{v[1]:.2f}, {v[2]:.2f}]" for v in vals) + " |")
    for name, pop in splits:
        for a, b in (("ppr", "bm25"), ("hybrid", "bm25"), ("hybrid", "anchor+bm25")):
            d = paired_diff([hit(r[f"node_rank_{a}"], 10) for r in pop], [hit(r[f"node_rank_{b}"], 10) for r in pop], rng)
            S["rq2"][f"split/{name}/diff/{a}-{b}@10"] = d
            md.append(f"\n[{name}] paired {a} - {b} node hit@10: {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}], P(diff<=0)={d[3]:.3f}")

    md.append("\n## Hybrid weight sensitivity (node-level; weights = anchor+bm25, bm25, ppr, emb)\n\n| weights | @1 | @10 |\n|---|---|---|")
    for w in ("w1111", "w2100", "w2110", "w2101", "w4110"):
        if f"node_rank_hyb_{w}" in node_set[0]:
            a1 = np.mean([hit(r[f"node_rank_hyb_{w}"], 1) for r in node_set]); a10 = np.mean([hit(r[f"node_rank_hyb_{w}"], 10) for r in node_set])
            S["rq2"][f"sens/{w}"] = (a1, a10)
            md.append(f"| {w} | {a1:.3f} | {a10:.3f} |")

    # per repository
    md.append("\n## Per repository (node-level eval set)\n\n| repo | tasks | names gold | median nodes | bm25 @10 | hybrid @10 |\n|---|---|---|---|---|---|")
    for repo in sorted({r["repo"] for r in node_set}):
        pop = [r for r in node_set if r["repo"] == repo]
        md.append(f"| {repo} | {len(pop)} | {sum(r['anchor_hits_gold'] for r in pop)} | {int(np.median([r['n_nodes'] for r in pop]))} | "
                  f"{np.mean([hit(r['node_rank_bm25'], 10) for r in pop]):.2f} | {np.mean([hit(r['node_rank_hybrid'], 10) for r in pop]):.2f} |")

    # ---- figures ----
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    ks = [1, 2, 3, 5, 10, 20, 50]
    for rk in RANKERS:
        for j, (level, pop) in enumerate((("node", node_set), ("file", file_set))):
            ax[j].plot(ks, [np.mean([hit(r[f"{level}_rank_{rk}"], k) for r in pop]) for k in ks], marker="o", ms=3, label=rk)
    for j, t in enumerate(("function/class (graph node)", "file")):
        ax[j].set_xscale("log"); ax[j].set_xticks(ks); ax[j].set_xticklabels(ks)
        ax[j].set_xlabel("k"); ax[j].set_ylabel("hit@k"); ax[j].set_title(t); ax[j].grid(alpha=.3)
    ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(ROOT / "figures" / "hit_at_k.png", dpi=160)

    fig, ax = plt.subplots(figsize=(5, 3.2))
    labels = ["0", "1", "2", "3", "4-6", ">6/none"]
    cnt = [sum(1 for d in dists if d == 0), sum(1 for d in dists if d == 1), sum(1 for d in dists if d == 2),
           sum(1 for d in dists if d == 3), sum(1 for d in dists if d is not None and 4 <= d <= 6),
           sum(1 for d in dists if d is None or d > 6)]
    S["hop_hist"] = dict(zip(labels, cnt))
    ax.bar(labels, cnt, color="#4a6fa5")
    ax.set_xlabel("call-graph hops from nearest issue anchor to nearest gold node")
    ax.set_ylabel("tasks"); fig.tight_layout(); fig.savefig(ROOT / "figures" / "anchor_hops.png", dpi=160)

    fig, ax = plt.subplots(figsize=(8, 3.4))
    w = 0.16
    for j, rk in enumerate(SUB):
        vals = [np.mean([hit(r[f"node_rank_{rk}"], 10) for r in pop]) for _, pop in splits]
        ax.bar(np.arange(len(splits)) + (j - 2) * w, vals, w, label=rk)
    ax.set_xticks(range(len(splits)))
    ax.set_xticklabels([f"{name}\n(n={len(pop)})" for name, pop in splits], fontsize=8)
    ax.set_ylabel("function-level hit@10"); ax.set_ylim(0, 1); ax.legend(fontsize=7, ncol=5, loc="upper right")
    ax.grid(axis="y", alpha=.3); fig.tight_layout(); fig.savefig(ROOT / "figures" / "regimes.png", dpi=160)

    # ---- RQ3 (LLM) if present ----
    llm = ROOT / "results" / "llm_localization.jsonl"
    if llm.exists():
        L = [json.loads(l) for l in open(llm)]
        conds = sorted({x["condition"] for x in L})
        ids = sorted({x["instance_id"] for x in L if all(
            any(y["instance_id"] == x["instance_id"] and y["condition"] == c for y in L) for c in conds)})
        md.append(f"\n## RQ3 Gemma 4 E4B localization (n={len(ids)} tasks with all conditions)\n")
        md.append("| condition | func hit@1 | func hit@5 | file hit@1 | file hit@5 | parse ok |\n|---|---|---|---|---|---|")
        S["rq3"] = {}
        by = {(x["instance_id"], x["condition"]): x for x in L}
        for c in conds:
            e = {}
            for m in ("func_hit1", "func_hit5", "file_hit1", "file_hit5", "parsed"):
                e[m] = boot_ci([float(by[(i, c)][m]) for i in ids], rng)
            S["rq3"][c] = e
            md.append(f"| {c} | " + " | ".join(f"{e[m][0]:.3f} [{e[m][1]:.2f}, {e[m][2]:.2f}]"
                                               for m in ("func_hit1", "func_hit5", "file_hit1", "file_hit5", "parsed")) + " |")
        if "tree" in conds:
            for c in conds:
                if c == "tree":
                    continue
                for m in ("func_hit1", "file_hit1"):
                    d = paired_diff([by[(i, c)][m] for i in ids], [by[(i, "tree")][m] for i in ids], rng)
                    S["rq3"][f"diff/{c}-tree/{m}"] = d
                    md.append(f"\npaired {c} - tree {m}: {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}], P(diff<=0)={d[3]:.3f}")

        # retrieval prior alone, scored by the same function as the model (candidate #1 and top-5 of the 20 shown)
        import sys
        sys.path.insert(0, str(ROOT))
        from scripts.llm_localize import candidate_lines, score
        from wtfl.rankers import is_test_node
        labs = {l["instance_id"]: l for l in map(json.loads, open(ROOT / "results" / "gold_labels.jsonl"))}
        for name in ("bm25", "hybrid"):
            c = f"{name}_top20 prior alone"
            for i in ids:
                lab = labs[i]
                idx = json.loads((ROOT / "results" / "index" / f"{lab['graph_key']}.json").read_text())
                rk = json.loads((ROOT / "results" / "rankings" / f"{i}.json").read_text())
                gp = sorted({(f["path"], s["qualname"]) for f in lab["files"] for s in f["symbols"]
                             if s["node"] and not is_test_node(s["node"])})
                gf = {f["path"] for f in lab["files"] if not f["is_new"]}
                by[(i, c)] = {**score(candidate_lines(rk[name], idx["node2loc"], idx["file_defs"]), gp, gf), "parsed": True}
            e = {m: boot_ci([float(by[(i, c)][m]) for i in ids], rng) for m in ("func_hit1", "func_hit5", "file_hit1", "file_hit5")}
            S["rq3"][c] = e
            md.append(f"| {c} | " + " | ".join(f"{e[m][0]:.3f} [{e[m][1]:.2f}, {e[m][2]:.2f}]"
                                               for m in ("func_hit1", "func_hit5", "file_hit1", "file_hit5")) + " | n/a |")
            for m in ("func_hit1", "file_hit1"):
                d = paired_diff([by[(i, f"{name}_top20")][m] for i in ids], [by[(i, c)][m] for i in ids], rng)
                S["rq3"][f"diff/{name}_top20-prior_alone/{m}"] = d
                md.append(f"\npaired Gemma({name}_top20) - prior alone {m}: {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}], P(diff<=0)={d[3]:.3f}")
        d = paired_diff([by[(i, "hybrid_top20")]["func_hit1"] for i in ids], [by[(i, "bm25_top20")]["func_hit1"] for i in ids], rng)
        S["rq3"]["diff/hybrid_top20-bm25_top20/func_hit1"] = d
        md.append(f"\npaired hybrid_top20 - bm25_top20 func_hit1: {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}], P(diff<=0)={d[3]:.3f}")
        P = {r["instance_id"]: r for r in rows}
        # recall bound: model hit@1 with vs without the gold among the 20 candidates shown
        for name in ("bm25", "hybrid"):
            inc = [i for i in ids if P[i][f"node_rank_{name}"] is not None and P[i][f"node_rank_{name}"] <= 20]
            out = [i for i in ids if i not in inc]
            h_in = int(sum(by[(i, f"{name}_top20")]["func_hit1"] for i in inc))
            h_out = int(sum(by[(i, f"{name}_top20")]["func_hit1"] for i in out))
            S["rq3"][f"recall/{name}"] = {"gold_in_top20": [h_in, len(inc)], "gold_not_in_top20": [h_out, len(out)]}
            md.append(f"\nGemma+{name}_top20 func_hit1: gold in list {h_in}/{len(inc)}, gold not in list {h_out}/{len(out)}")
        # by regime (same split as RQ2)
        reg = {i: "issue names a gold node" if P[i]["anchor_hits_gold"] else
               ("issue names other code" if P[i]["n_anchors"] else "issue names no code") for i in ids}
        cols = ["tree", "bm25_top20", "hybrid_top20", "bm25_top20 prior alone", "hybrid_top20 prior alone"]
        md.append("\n| regime (func hit@1) | n | " + " | ".join(cols) + " |\n|---|---|" + "---|" * len(cols))
        S["rq3"]["regimes"] = {}
        for g in ("issue names a gold node", "issue names other code", "issue names no code"):
            gi = [i for i in ids if reg[i] == g]
            v = {c: float(np.mean([by[(i, c)]["func_hit1"] for i in gi])) for c in cols}
            S["rq3"]["regimes"][g] = {"n": len(gi), **v}
            md.append(f"| {g} | {len(gi)} | " + " | ".join(f"{v[c]:.3f}" for c in cols) + " |")
        fig, ax = plt.subplots(figsize=(7, 3.4))
        cs = ["tree", "bm25_top20 prior alone", "bm25_top20", "hybrid_top20 prior alone", "hybrid_top20"]
        lab_ = ["Gemma\nfile tree", "BM25 #1\n(no LLM)", "Gemma\n+BM25 top-20", "hybrid #1\n(no LLM)", "Gemma\n+hybrid top-20"]
        mu = [S["rq3"][c]["func_hit1"] for c in cs]
        ax.bar(range(len(cs)), [m[0] for m in mu], yerr=[[m[0] - m[1] for m in mu], [m[2] - m[0] for m in mu]],
               color=["#888", "#9ab", "#357", "#ca9", "#a53"], capsize=3)
        ax.set_xticks(range(len(cs))); ax.set_xticklabels(lab_, fontsize=8)
        ax.set_ylabel("function-level hit@1"); ax.set_ylim(0, .7); ax.grid(axis="y", alpha=.3)
        ax.set_title(f"Gemma 4 E4B localization, n={len(ids)} tasks (95% bootstrap CI)", fontsize=9)
        fig.tight_layout(); fig.savefig(ROOT / "figures" / "rq3.png", dpi=160)

    (ROOT / "results" / "tables.md").write_text("\n".join(md) + "\n")
    (ROOT / "results" / "summary.json").write_text(json.dumps(S, indent=1))
    print("\n".join(md))


if __name__ == "__main__":
    main()
