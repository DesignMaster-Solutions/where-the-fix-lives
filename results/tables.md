# Results

Tasks: 129; with a gold graph node (function-level eval): 115; with a gold existing .py file (file-level eval): 128.

## RQ1 structure (mean [95% bootstrap CI], count/total)

| quantity | value |
|---|---|
| only_new_files | 0.01 [0.00, 0.02] 1/129 |
| has_new_file | 0.09 [0.04, 0.14] 11/129 |
| single_file | 0.70 [0.62, 0.78] 90/129 |
| module_level_only | 0.10 [0.05, 0.16] 13/128 |
| file_anchor_any | 0.09 [0.04, 0.13] 11/128 |
| file_anchor_hits_gold | 0.08 [0.03, 0.12] 10/128 |
| symbol_anchor_any | 0.48 [0.39, 0.57] 55/115 |
| anchor_hits_gold_node | 0.27 [0.19, 0.35] 31/115 |
| gold_isolated_in_call_graph | 0.01 [0.00, 0.03] 1/115 |
| gold_has_embedding | 1.00 [1.00, 1.00] 115/115 |
| gold within 0 hops of an anchor (tasks with anchors) | 0.56 [0.44, 0.69] 31/55 |
| gold within 1 hops of an anchor (tasks with anchors) | 0.62 [0.49, 0.75] 34/55 |
| gold within 2 hops of an anchor (tasks with anchors) | 0.69 [0.56, 0.80] 38/55 |
| gold within 3 hops of an anchor (tasks with anchors) | 0.82 [0.71, 0.91] 45/55 |

## RQ2 node-level hit@k (mean [95% CI]), n=115

| ranker | @1 | @5 | @10 | @20 | MRR |
|---|---|---|---|---|---|
| random | 0.000 [0.00, 0.00] | 0.017 [0.00, 0.04] | 0.052 [0.02, 0.10] | 0.087 [0.04, 0.14] | 0.019 |
| bm25 | 0.122 [0.07, 0.18] | 0.391 [0.30, 0.48] | 0.496 [0.40, 0.58] | 0.557 [0.46, 0.64] | 0.247 |
| emb_knn | 0.096 [0.04, 0.15] | 0.122 [0.07, 0.18] | 0.191 [0.12, 0.27] | 0.252 [0.17, 0.34] | 0.127 |
| ppr | 0.113 [0.06, 0.17] | 0.348 [0.27, 0.43] | 0.417 [0.33, 0.50] | 0.496 [0.40, 0.59] | 0.226 |
| anchor+bm25 | 0.217 [0.15, 0.30] | 0.443 [0.36, 0.53] | 0.530 [0.44, 0.63] | 0.609 [0.52, 0.70] | 0.324 |
| hybrid | 0.226 [0.15, 0.31] | 0.443 [0.35, 0.53] | 0.539 [0.45, 0.63] | 0.626 [0.54, 0.71] | 0.338 |

paired hybrid - bm25 hit@1: +0.104 [+0.026, +0.183], P(diff<=0)=0.003

paired hybrid - bm25 hit@10: +0.043 [-0.009, +0.104], P(diff<=0)=0.083

paired ppr - bm25 hit@1: -0.009 [-0.087, +0.061], P(diff<=0)=0.638

paired ppr - bm25 hit@10: -0.078 [-0.157, +0.000], P(diff<=0)=0.984

paired emb_knn - bm25 hit@1: -0.026 [-0.104, +0.052], P(diff<=0)=0.755

paired emb_knn - bm25 hit@10: -0.304 [-0.409, -0.208], P(diff<=0)=1.000

paired hybrid - anchor+bm25 hit@1: +0.009 [-0.035, +0.052], P(diff<=0)=0.402

paired hybrid - anchor+bm25 hit@10: +0.009 [-0.043, +0.061], P(diff<=0)=0.439

## RQ2 file-level hit@k (mean [95% CI]), n=128

| ranker | @1 | @5 | @10 | @20 | MRR |
|---|---|---|---|---|---|
| random | 0.008 [0.00, 0.02] | 0.203 [0.14, 0.27] | 0.414 [0.34, 0.50] | 0.594 [0.51, 0.68] | 0.127 |
| bm25 | 0.312 [0.23, 0.39] | 0.648 [0.56, 0.73] | 0.781 [0.70, 0.85] | 0.906 [0.85, 0.95] | 0.474 |
| emb_knn | 0.250 [0.18, 0.33] | 0.562 [0.48, 0.64] | 0.672 [0.59, 0.75] | 0.773 [0.70, 0.84] | 0.388 |
| ppr | 0.352 [0.27, 0.44] | 0.656 [0.57, 0.73] | 0.773 [0.70, 0.84] | 0.867 [0.80, 0.92] | 0.488 |
| anchor+bm25 | 0.367 [0.29, 0.45] | 0.664 [0.59, 0.74] | 0.797 [0.73, 0.87] | 0.898 [0.84, 0.95] | 0.506 |
| hybrid | 0.406 [0.33, 0.49] | 0.703 [0.62, 0.78] | 0.820 [0.75, 0.88] | 0.906 [0.86, 0.95] | 0.547 |

paired hybrid - bm25 hit@1: +0.094 [+0.016, +0.164], P(diff<=0)=0.011

paired hybrid - bm25 hit@10: +0.039 [+0.000, +0.086], P(diff<=0)=0.064

paired ppr - bm25 hit@1: +0.039 [-0.055, +0.141], P(diff<=0)=0.251

paired ppr - bm25 hit@10: -0.008 [-0.070, +0.055], P(diff<=0)=0.623

paired emb_knn - bm25 hit@1: -0.062 [-0.156, +0.031], P(diff<=0)=0.916

paired emb_knn - bm25 hit@10: -0.109 [-0.203, -0.016], P(diff<=0)=0.990

paired hybrid - anchor+bm25 hit@1: +0.039 [-0.016, +0.094], P(diff<=0)=0.103

paired hybrid - anchor+bm25 hit@10: +0.023 [-0.016, +0.062], P(diff<=0)=0.158

## RQ2 node hit@10 by anchoring

| subset | n | bm25 | ppr | emb_knn | hybrid |
|---|---|---|---|---|---|
| issue names a gold symbol/file | 31 | 0.774 | 0.871 | 0.484 | 0.935 |
| no lexical anchor on gold | 84 | 0.393 | 0.250 | 0.083 | 0.393 |
