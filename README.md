# Where the Fix Lives

Code-graph structure of bug localization in the Gemma 4 Developer Agent benchmark, and a
training-free localization prior for small local models.

Author: Alan De Bortolo, Design Master Solutions LLC. License: Apache-2.0.
Submitted to the Kaggle "Google - The Gemma 4 Developer Agent Paper Track" (2026).

## What is here

| path | what it does |
|---|---|
| `wtfl/patch.py` | parses a unified diff into touched files and old-side line numbers |
| `wtfl/repo_index.py` | maps the benchmark's graph nodes (dotted symbol paths, no file info) to files and line spans at the task's base commit, by parsing the source with `ast` |
| `wtfl/anchors.py` | finds what an issue names explicitly: identifiers, `.py` paths, traceback frames, and the graph nodes they match |
| `wtfl/rankers.py` | training-free localization rankers over the provided call graph and node embeddings: BM25, embedding kNN, personalized PageRank, anchor-first BM25, and a reciprocal-rank-fusion hybrid |
| `scripts/build_labels.py` | gold localization labels (file / function / graph node) for every task |
| `scripts/run_rankers.py` | RQ1 structure statistics and RQ2 ranker evaluation per task |
| `scripts/llm_localize.py` | RQ3: Gemma 4 E4B (local, llama.cpp) localization with and without the prior |
| `scripts/score_llm.py` | re-scores the stored Gemma predictions against the gold labels |
| `scripts/analyze.py` | bootstrap confidence intervals, tables (`results/tables.md`) and figures |
| `results/llm_predictions.jsonl` | raw Gemma 4 E4B predictions (our model outputs; no benchmark data) |
| `results/tables.md`, `results/summary.json`, `figures/` | aggregate results reported in the paper |

## Data policy

The task set, gold patches, graphs and embeddings belong to the Kaggle competition
`gemma-4-developer-agent` and may not be redistributed to non-participants. This repository
therefore ships **code and aggregate results only**. Per-task gold labels and rankings are
regenerated from the competition data by the scripts below (or by the public Kaggle notebook,
which runs the whole pipeline on the attached competition data).

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
# DATA holds the competition files: tasks.jsonl, graphs/, embeddings/
# plus git clones of the four upstream repos under DATA/repos/{fastapi,rich,requests,httpx}
for r in fastapi/fastapi Textualize/rich psf/requests encode/httpx; do git clone https://github.com/$r DATA/repos/${r#*/}; done
.venv/bin/python scripts/build_labels.py DATA      # gold labels
.venv/bin/python scripts/run_rankers.py DATA       # RQ1 + RQ2
.venv/bin/python scripts/score_llm.py score        # RQ3 from stored predictions
.venv/bin/python scripts/analyze.py                # tables + figures
.venv/bin/python -m pytest -q tests
```

Re-running the model itself (RQ3) needs `llama-server` with the free GGUF
`ggml-org/gemma-4-E4B-it-GGUF` (Q8_0):

```bash
llama-server -m gemma-4-E4B-it-Q8_0.gguf --port 8931 -ngl 99 --parallel 2 -c 65536
.venv/bin/python scripts/llm_localize.py DATA
```
