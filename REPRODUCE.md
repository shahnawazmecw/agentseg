# Reproducing the AgentSeg results

Everything below ran on one laptop (AMD Ryzen 5 7530U, 15.4 GB RAM, Windows 11, Python 3.12, Rust 1.99 GNU toolchain). Commands are run from `agentseg/` unless noted. Long steps are resumable: rerun the same command until it prints "all … done".

## 1. Data (see `DATASETS.md` for sources and licences)

| Folder under `datasets/` | How it was obtained |
|---|---|
| `D1_misuse_detection_containers` | Kaggle `yigitsever/misuse-detection-in-containers-dataset` |
| `D2_alibaba_microservices_v2022` | `aliopentrace.oss-cn-beijing.aliyuncs.com/v2022MicroservicesTraces`: CallGraph_0–39, MSMetrics_0–3, NodeMetrics_0 (first 2 hours) |
| `D3_lanl_sample` | Kaggle `omniaayman1/comprehensive-multi-source-cyber-security-events` (parquet: auth, flows, dns, redteam) |
| `D4_mcp_security_bench` | Hugging Face `DongsenZhang/MSB` and GitHub `dongsenzhang/MSB` |
| `D5_injecagent` | Kaggle `alexbenjaminwarner/injecagent` |
| `D6_agentdojo` | GitHub `ethz-spylab/agentdojo` |

Python packages: `pyarrow`, `numpy`, `matplotlib`, `python-docx`, `pytest`. E6 also needs Ollama with `qwen2.5:1.5b` and a separate venv with AgentDojo: `python -m venv .venv_agentdojo` and `.venv_agentdojo/Scripts/python -m pip install ./datasets/D6_agentdojo`.

## 2. Tests

`python -m pytest -q tests`: 16 tests (IMS worked examples and invariants, group table = per-pair rules, incremental composition, agent policy).

## 3. Experiments

| Step | Command | Time on the laptop | Output in `results/` |
|---|---|---|---|
| IMS baseline | `python bench/ims_repro.py --deadline 480` (repeat), then `python bench/summarize_ims.py` | ~1 h | `ims_repro*.{jsonl,md}` |
| Alibaba extraction | `python e1/prep_alibaba.py 0 1 … 24` | ~47 s per window | `../datasets/derived/alibaba_callgraph_w*.pkl` |
| E1 | `python e1/run_e1.py`, `python e1/pairwise_points.py`, `python e1/summarize_e1.py` | ~15 min | `e1*.{jsonl,md}` |
| Pod lifetimes | `python e2/prep_lifecycle.py` | ~1.5 min | `../datasets/derived/alibaba_pod_lifecycle.pkl` |
| E2 | `python e2/drift.py`, `python e2/churn.py` | ~10 min | `e2_*` |
| E3 | `python e3/run_e3.py` | ~3 min | `e3*` |
| E4 | `python e4/prep_lanl.py --deadline 440` (repeat), then `python e4/run_e4.py` | ~15 min | `e4*` |
| E5 | `python e5/run_e5.py` | < 1 min | `e5*` |
| E6 | `../.venv_agentdojo/Scripts/python e6/run_e6.py --deadline 520` (repeat; Ollama running) | ~35 min | `e6*`, `e6_runs/` |
| E7 | `python e7/prep_e7.py`; `cargo build --release` in `e7/rust_bench`; run `e7/rust_bench/target/release/agentseg_bench ../datasets/derived/e7` five times into `results/e7_rust_runs.jsonl` (median written to `e7_rust.json`) | ~5 min | `e7_*` |

## 4. Figures

From `paper/`: `python figs.py` redraws the five figures of the paper from `agentseg/results` into `paper/fig/` (PNG at 600 dpi and PDF).

## Notes

- Files named `superseded_*` are results from earlier, corrected versions of an experiment, kept for the record; `agentseg/README.md` says why each was superseded.
- Absolute times vary between runs on this laptop (up to about 3× for the Rust micro-benchmark); medians are reported.
