"""Re-score Gemma predictions against gold labels, so RQ3 is reproducible without re-running the model.

Usage:
  python scripts/score_llm.py export   # results/llm_localization.jsonl -> results/llm_predictions.jsonl (no gold)
  python scripts/score_llm.py score    # results/llm_predictions.jsonl + gold_labels -> results/llm_localization.jsonl
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.llm_localize import score  # noqa: E402
from wtfl.rankers import is_test_node  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KEEP = ("instance_id", "condition", "preds", "parsed", "finish_reason", "prompt_tokens",
        "completion_tokens", "reasoning_chars", "secs")


def main(mode):
    res = ROOT / "results"
    if mode == "export":
        with open(res / "llm_predictions.jsonl", "w") as fh:
            for x in map(json.loads, open(res / "llm_localization.jsonl")):
                fh.write(json.dumps({k: x.get(k) for k in KEEP}) + "\n")
        return
    labels = {l["instance_id"]: l for l in map(json.loads, open(res / "gold_labels.jsonl"))}
    with open(res / "llm_localization.jsonl", "w") as fh:
        for x in map(json.loads, open(res / "llm_predictions.jsonl")):
            lab = labels[x["instance_id"]]
            pairs = {(f["path"], s["qualname"]) for f in lab["files"] for s in f["symbols"]
                     if s["node"] and not is_test_node(s["node"])}
            files = {f["path"] for f in lab["files"] if not f["is_new"]}
            fh.write(json.dumps({**x, **score(x["preds"], pairs, files)}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
