"""RQ3: does a small local model (Gemma 4 E4B via llama.cpp) localize better with a graph prior?

Conditions (same issue text, same output format):
  tree          issue + every non-test .py path in the repo
  bm25_top20    issue + 20 candidate functions/classes from BM25
  hybrid_top20  issue + 20 candidate functions/classes from the hybrid graph ranker

Usage: python scripts/llm_localize.py DATA_DIR [--url http://127.0.0.1:8931] [--limit N]
Appends to results/llm_localization.jsonl (resumable).
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wtfl.rankers import is_test_node  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "llm_localization.jsonl"
MAX_ISSUE = 6000
INSTR = ("You are localizing a code change. Read the issue and decide which existing Python functions or "
         "classes must be edited to resolve it. Answer ONLY with a JSON list of up to 5 strings, most likely "
         "first, each formatted exactly as \"path/to/file.py::QualifiedName\" (e.g. \"pkg/mod.py::Class.method\").")


def is_test_path(p: str) -> bool:
    parts = p.split("/")
    return any(s in ("tests", "test") for s in parts[:-1]) or parts[-1].startswith("test_")


def chat(url, prompt, max_tokens=4096):
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "temperature": 0,
                       "max_tokens": max_tokens, "seed": 0}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    ch = d["choices"][0]
    usage = {**d.get("usage", {}), "finish_reason": ch.get("finish_reason"),
             "reasoning_chars": len(ch["message"].get("reasoning_content") or "")}
    return ch["message"].get("content") or "", usage


def parse(text):
    m = re.search(r"\[.*?\]", text, re.S)
    if m:
        try:
            v = json.loads(m.group(0))
            return [str(x) for x in v if isinstance(x, str)], True
        except json.JSONDecodeError:
            pass
    return re.findall(r"[\w./-]+\.py::[\w.]+", text), False


def candidate_lines(ranking, node2loc, file_defs, n=20):
    lines = []
    for node in ranking:
        loc = node2loc.get(node)
        if not loc:
            continue
        qual = next((q for nn, q, s, e in file_defs.get(loc[0], []) if nn == node), node.split(".")[-1])
        lines.append(f"{loc[0]}::{qual}")
        if len(lines) == n:
            break
    return lines


def score(preds, gold_pairs, gold_files):
    def fhit(p, k):
        return any(x.split("::")[0].lstrip("./") in gold_files for x in p[:k])

    def shit(p, k):
        for x in p[:k]:
            if "::" not in x:
                continue
            f, q = x.split("::", 1)
            f = f.lstrip("./")
            if any(f == gf and (q == gq or gq.startswith(q + ".")) for gf, gq in gold_pairs):
                return True
        return False
    return {"func_hit1": shit(preds, 1), "func_hit5": shit(preds, 5),
            "file_hit1": fhit(preds, 1), "file_hit5": fhit(preds, 5)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path)
    ap.add_argument("--url", default="http://127.0.0.1:8931")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    tasks = {json.loads(l)["instance_id"]: json.loads(l) for l in open(a.data / "tasks.jsonl")}
    labels = [json.loads(l) for l in open(ROOT / "results" / "gold_labels.jsonl")]
    labels = [l for l in labels if any(not is_test_node(n) for n in l["gold_nodes"])]
    if a.limit:
        labels = labels[:a.limit]
    done = set()
    if OUT.exists():
        done = {(x["instance_id"], x["condition"]) for x in map(json.loads, open(OUT))}

    jobs = []
    for lab in labels:
        t = tasks[lab["instance_id"]]
        idx = json.loads((ROOT / "results" / "index" / f"{lab['graph_key']}.json").read_text())
        ranks = json.loads((ROOT / "results" / "rankings" / f"{lab['instance_id']}.json").read_text())
        gold_pairs = sorted({(f["path"], s["qualname"]) for f in lab["files"] for s in f["symbols"]
                             if s["node"] and not is_test_node(s["node"])})
        gold_files = {f["path"] for f in lab["files"] if not f["is_new"]}
        issue = t["problem_statement"][:MAX_ISSUE]
        tree = "\n".join(p for p in idx["py_files"] if not is_test_path(p))
        ctx = {
            "tree": f"Repository Python files:\n{tree}",
            "bm25_top20": "Candidate locations from a retrieval prior, most likely first (may all be wrong):\n" + "\n".join(
                candidate_lines(ranks["bm25"], idx["node2loc"], idx["file_defs"])),
            "hybrid_top20": "Candidate locations from a retrieval prior, most likely first (may all be wrong):\n" + "\n".join(
                candidate_lines(ranks["hybrid"], idx["node2loc"], idx["file_defs"])),
        }
        for cond, c in ctx.items():
            if (lab["instance_id"], cond) in done:
                continue
            prompt = f"{INSTR}\n\nRepository: {t['repo']}\n\nIssue:\n{issue}\n\n{c}\n\nJSON list:"
            jobs.append((lab["instance_id"], cond, prompt, gold_pairs, gold_files))

    def run(job):
        iid, cond, prompt, gold_pairs, gold_files = job
        t0 = time.time()
        try:
            text, usage = chat(a.url, prompt)
        except Exception as e:  # noqa: BLE001 - record the failure, keep going
            text, usage = f"ERROR {e}", {}
        preds, ok = parse(text)
        return {"instance_id": iid, "condition": cond, "preds": preds[:5], "parsed": ok, "raw": text[:2000],
                "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                "finish_reason": usage.get("finish_reason"), "reasoning_chars": usage.get("reasoning_chars"), "secs": round(time.time() - t0, 1),
                **score(preds, gold_pairs, gold_files)}

    with ThreadPoolExecutor(a.workers) as ex, open(OUT, "a") as fh:
        for r in ex.map(run, jobs):
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            print(r["instance_id"], r["condition"], r["func_hit5"], r["file_hit1"], r["secs"], flush=True)


if __name__ == "__main__":
    main()
