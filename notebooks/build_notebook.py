"""Write the public Kaggle notebook (reproduces every number in the paper from the competition data)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

cells = [
    ("md", """# Where the Fix Lives: reproduction notebook

This notebook reproduces every number and figure of the paper *Where the Fix Lives: code-graph
structure of bug localization, and a training-free graph prior for small local models*
(Alan De Bortolo, Design Master Solutions LLC) from the attached competition data of
`gemma-4-developer-agent`. Code: https://github.com/DesignMaster-Solutions/where-the-fix-lives (Apache-2.0).

Pipeline: (1) gold localization labels from each task's gold patch, mapped onto the provided code
graph by parsing the upstream source at the task's `base_commit`; (2) RQ1 structure statistics;
(3) RQ2 training-free rankers over the provided graph and embeddings; (4) RQ3 re-scoring of the
stored Gemma 4 E4B predictions (the model itself ran locally with llama.cpp; see the repo)."""),
    ("code", """import glob, os, subprocess, sys
src = glob.glob('/kaggle/input/**/tasks.jsonl', recursive=True)
assert src, 'attach the gemma-4-developer-agent competition data'
COMP = os.path.dirname(src[0]); print('competition data:', COMP)
W = '/kaggle/working'
subprocess.run(['git', 'clone', '-q', 'https://github.com/DesignMaster-Solutions/where-the-fix-lives', f'{W}/wtfl'], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'rank_bm25==0.2.2'], check=True)
DATA = f'{W}/data'; os.makedirs(f'{DATA}/repos', exist_ok=True)
for name in ('tasks.jsonl', 'graphs', 'embeddings'):
    if not os.path.exists(f'{DATA}/{name}'):
        os.symlink(f'{COMP}/{name}', f'{DATA}/{name}')
for r in ('fastapi/fastapi', 'Textualize/rich', 'psf/requests', 'encode/httpx'):
    d = f"{DATA}/repos/{r.split('/')[1]}"
    if not os.path.exists(d):
        subprocess.run(['git', 'clone', '-q', f'https://github.com/{r}', d], check=True)
os.chdir(f'{W}/wtfl'); print(subprocess.run(['git', 'log', '-1', '--oneline'], capture_output=True, text=True).stdout)"""),
    ("md", "## 1. Gold localization labels"),
    ("code", """!python scripts/build_labels.py {DATA} | tail -3
import json, collections
L = [json.loads(l) for l in open('results/gold_labels.jsonl')]
c = collections.Counter()
for l in L:
    for f in l['files']:
        for s in f['symbols']:
            c['in a graph node' if s['node'] else ('in a def missing from the graph' if s['qualname'] else 'module-level')] += 1
print(len(L), 'tasks;', sum(1 for l in L if l['gold_nodes']), 'with >=1 gold graph node; touched old-side lines:', dict(c))"""),
    ("md", "## 2. RQ1 structure and RQ2 rankers"),
    ("code", "!python scripts/run_rankers.py {DATA} | tail -3"),
    ("md", "## 3. RQ3: re-score the stored Gemma 4 E4B predictions, then all tables"),
    ("code", """import os
if os.path.exists('results/llm_predictions.jsonl'):
    !python scripts/score_llm.py score
!python scripts/analyze.py"""),
    ("code", """from IPython.display import Image, display
display(Image('figures/hit_at_k.png')); display(Image('figures/anchor_hops.png'))
import glob
for f in sorted(glob.glob('figures/*.png')):
    print(f)"""),
    ("code", "!python -m pytest -q tests"),
]

nb = {"cells": [], "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                                "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
for i, (kind, text) in enumerate(cells):
    c = {"cell_type": "markdown" if kind == "md" else "code", "id": f"c{i}", "metadata": {},
         "source": text.splitlines(keepends=True)}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    nb["cells"].append(c)
(HERE / "where-the-fix-lives.ipynb").write_text(json.dumps(nb, indent=1))
(HERE / "kernel-metadata.json").write_text(json.dumps({
    "id": "designmasterdms/where-the-fix-lives-reproduction",
    "title": "Where the Fix Lives - reproduction",
    "code_file": "where-the-fix-lives.ipynb", "language": "python", "kernel_type": "notebook",
    "is_private": False, "enable_gpu": False, "enable_internet": True,
    "competition_sources": ["gemma-4-developer-agent"], "dataset_sources": [], "kernel_sources": [],
}, indent=1))
print("ok")
