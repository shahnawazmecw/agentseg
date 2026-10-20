# AgentSeg

Code, experiment scripts and results for the paper *AgentSeg: Group-Level, Verifiable Micro-Segmentation for Microservices and AI Agents at Production Scale* (S. Ahmad, submitted to IEEE Transactions on Computers, 2026).

AgentSeg is a micro-segmentation system for microservices and AI agents. It keeps the policy algebra of IMS (Ma et al., IEEE TDSC 2025), which detects conflicts between policies and checks reachability, and changes what a verified policy is compiled into: rules between endpoint groups plus a table that maps each endpoint to its group, instead of one rule per pair of endpoints. It also adds new intents incrementally, and it treats AI agents and their tool servers as endpoints whose groups come from verified identities and whose relations name a tool and a parameter scope.

## Contents

| Path | What it holds |
|---|---|
| `agentseg/ims/` | A re-implementation of IMS (its Definitions 1–6 and Algorithms 1–6, with both of its optimizations), used as the base and the baseline |
| `agentseg/core/` | AgentSeg: group-level compilation (`groups.py`), incremental composition (`incremental.py`), agents and tool servers as endpoints (`agents.py`) |
| `agentseg/tests/` | 16 tests: the worked examples of the IMS paper, and checks that group decisions, incremental composition and endpoint updates equal full recomputation |
| `agentseg/bench/`, `agentseg/e1/` … `agentseg/e7/` | One folder per experiment, including a Rust decision benchmark in `e7/rust_bench/` (standard library only) |
| `agentseg/results/` | The results reported in the paper, as JSON/JSONL with Markdown summaries, and the AgentDojo run logs. Files named `superseded_*` come from earlier, corrected versions of an experiment; `agentseg/README.md` explains each one |
| `paper/figs.py`, `paper/fig/` | The script that draws the paper's figures from the results, and the figures |
| `DATASETS.md`, `datasets/README.md` | Where each input dataset comes from, its licence, and how it is used |
| `REPRODUCE.md` | Commands for every experiment, with run times on the machine we used |
| `EXPERIMENT_DESIGN.md` | The experiment plan written before the runs |

The input datasets are not included. They total about 20 GB and belong to their creators; `DATASETS.md` gives the download address of each.

## Quick start

```
pip install -r requirements.txt
cd agentseg
python -m pytest -q tests
```

The tests need no datasets. To repeat an experiment, download the datasets it uses into `datasets/` as listed in `REPRODUCE.md` and run the matching script; long steps can be stopped and resumed.

## Main results

All numbers were measured on one laptop (AMD Ryzen 5 7530U, 15.4 GB RAM) and come from `agentseg/results/`.

| Experiment | Result |
|---|---|
| E1, Alibaba v2022 trace (16,291 microservices, 314,363 pods) | IMS composes and verifies the policy in 63.3 ms and 69.3 ms, but its per-pair compilation would need 1.68 billion rules; AgentSeg compiles to 50,935 group rules in 20.5 ms and 17.0 MB |
| E2, 45 minutes of trace replay | Policy updates 9–63× faster than recomposition; a pod start or stop in microseconds |
| E3, Kubernetes attack flows | Least privilege denies 61.2% of attack flows, none of them exploits sent over allowed connections |
| E4, LANL red-team campaign | A pair policy learned before the attack denies all 749 red-team logons, at a cost of 5.40% of next-day legitimate logons |
| E5, MCP Security Bench (2,000 cases, offline) | 87.5% blocked with identity pinning and parameter scope, against 81.2% for tool-name allow-lists |
| E6, AgentDojo with a local model (480 runs) | Attack success falls from 4.2% to 0.0% with no change in utility |
| E7, decision cost (Rust) | 11.6 ns per decision; 388 million decisions per second on 8 threads |

## Citation

If you use this code, please cite the paper:

```
S. Ahmad, "AgentSeg: Group-level, verifiable micro-segmentation for microservices and AI agents at production scale,"
submitted to IEEE Transactions on Computers, 2026.
```

## Licence

The code is released under the MIT licence (`LICENSE`). The datasets keep their own licences, listed in `DATASETS.md`.
