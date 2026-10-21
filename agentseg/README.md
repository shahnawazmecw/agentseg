# AgentSeg code

Status 19 October 2026: the IMS re-implementation (the base system and main baseline) is done and checked against the IMS paper. All experiments E1–E7 are done (20 October 2026), and the ablation variant P1S of E5 was added on 21 October 2026.

E2 notes: the IMS Algorithm 6 comparison runs on a 203-microservice subset (1,933 pods, 205,219 per-pair rules), chosen as the services with the most pod events that keep per-pair rules under 5 M. A random subset had no pod events in minutes 30–75. Per-event times in the subset are single events timed with perf_counter, so sub-microsecond values are near the timer's resolution.

E1 notes: of 13.3 M call rows in window 0, 3.65 M with a non-microservice endpoint (USER, UNKNOWN, UNAVAILABLE) and 1,089 malformed rows are dropped. Per-pair compilation is measured only at 50 microservices (1.64 M rules); larger sizes are linear projections from that one point and must be labelled as such in the paper.

| Path | What it is |
|---|---|
| `ims/algebra.py` | Label forest, EPG to e_min conversion, optimization A (invalid label combinations), the `KV` table that switches optimization B (hash matching vs traversal) |
| `ims/policy.py` | Definitions 1–6, Algorithms 1, 2, 4, 5: composition, reachability verification and fix, intent deletion, constraint addition |
| `ims/compiler.py` | Algorithm 3 (compilation to flow rules, with the D_F / D_E dictionaries) and Algorithm 6 (EP relabelling) |
| `ims/datasets.py` | DS1, DS2 and 1000 EPs as in IMS Sec. VI; generator settings in `GENERATOR` |
| `tests/test_ims.py` | The paper's worked examples (Sec. IV-C, Fig. 5) and invariants: A and B do not change results; incremental EP update equals full recompilation; constraint addition keeps the original reachability; intent deletion keeps the maintained EPGs |
| `bench/ims_repro.py` | Resumable reproduction of IMS Sec. VII-B; writes `results/ims_repro.jsonl` |
| `bench/summarize_ims.py` | Writes `results/ims_repro_summary.md` |
| `core/groups.py` | AgentSeg group-level compilation: (group, R) -> groups plus an endpoint membership table; tested to make exactly IMS's per-pair decisions (`tests/test_groups.py`) |
| `e1/prep_alibaba.py` | Extracts the east-west topology of one Alibaba window to `../datasets/derived/` |
| `core/incremental.py` | AgentSeg incremental intent addition (per-triple filter, equal to full recomposition; `tests/test_incremental.py`) |
| `e2/prep_lifecycle.py` | Pod lifetimes (first/last minute) from MSMetrics_0–3 |
| `e2/drift.py`, `e2/churn.py` | E2: drift against learning window; churn replay of minutes 30–75. Results in `results/e2_*` |
| `core/agents.py` | Agents and tool servers as endpoints of the IMS algebra (kind, role, verified identity); relations (tool, scope); tested in `tests/test_agents.py` |
| `e5/run_e5.py` | E5: offline replay of MSB (2,000 cases) and InjecAgent (1,054 cases x 2 wordings) under five policy levels (P0 none, P1 tool-name allow-list, P1S names and parameter scope without identity pinning, used only in the ablation, P2 identity pinning, P3 identity pinning and scope); tool names and parameters of MSB's local servers read with `ast` (not run). `results/e5.json`, `results/e5_summary.md` |
| `e6/run_e6.py` | E6: AgentDojo banking, qwen2.5:1.5b via Ollama's OpenAI-compatible endpoint; no defense, AgentSeg tool intents, AgentSeg + parameter scope; 480 runs. Run with `../.venv_agentdojo/Scripts/python.exe`. `results/e6.json`, `results/e6_summary.md`, logs in `results/e6_runs/` |
| `e7/prep_e7.py`, `e7/rust_bench/` | E7: workload from Alibaba window 0 (8.16 M observed pod-to-pod calls), Rust decision benchmark (std only); `results/e7_rust.json` (median of 5 runs), `results/e7_python.json` |
| `e1/pairwise_points.py` | E1 supplement: measured per-pair compilation at 106 and 150 microservices on capped subsets; `results/e1_pairwise.jsonl` |
| `e3/run_e3.py` | E3: allow-lists learned from benign container flows at four granularities, attack blocking and time-split false denials; `results/e3.json`, `results/e3_summary.md`. Flows are put in client-to-service order first (0.8% of benign flows record the client's ephemeral port as the destination; without the fix the learned policy has 4,815 entries instead of 133) |
| `e4/prep_lanl.py`, `e4/run_e4.py` | E4: LANL network authentications aggregated column-wise with pyarrow (first time and count per key, 1.05 B events in ~13 min, resumable per file); policies learned before the first red-team event (41.9 h); red-team denials, legitimate denials in the next 24 h and over the remaining days, blast radius. `results/e4.json`, `results/e4_summary.md` |
| `e1/run_e1.py`, `e1/summarize_e1.py` | E1 on Alibaba windows 0 (policy) and 1 (reachability queries / drift); writes `results/e1.jsonl` and `results/e1_summary.md` |

Run: `python -m pytest -q tests`, then `python bench/ims_repro.py --deadline 480` repeatedly until it prints "all units done", then `python bench/summarize_ims.py`.

## Reproduction notes (for the paper's baseline section)

- **Generator.** IMS does not publish its generator's distributions. Ours is calibrated to the outputs IMS reports: about 10⁶ flow rules for 1000 EPs and about 6000 rules per relabelled EP. Constraint subjects are fully specified (one value per label type) and half of the constraints deny by default. An earlier setting with broad constraint subjects removed every intent; its results are kept as `results/superseded_ims_repro_broad_constraints.jsonl`.
- **Timing.** Timed sections run with Python's garbage collector off (as `timeit` does). With it on, full collections over millions of live sets doubled some times and made them fall as n grew; those results are in `results/superseded_ims_repro_gc_on*`.
- **Runs.** 10 runs per point for settings with optimization A; 3 runs for the slow settings without A (their spread is small).
- **Implementation choices.** Hash matching on the ingress side intersects each iE with the set of constraint subjects (iterating the smaller side, IMS Sec. V-F). The traversal baseline scans every intent entry for every constraint.
- **Results vs IMS.** Both optimizations help: (A, B) is 28–46× faster than (!A, !B) at the largest size. Times with (A, B) grow with n. EP relabelling takes 3.49 ± 1.09 ms with ~5,700 rules removed and added, where IMS reports ~5.05 ms with ~6,000. Compilation costs 0.47–0.55 µs per generated rule. Rule counts fall as n grows because compilation uses n constraints along with n intents; IMS Fig. 14 shows them rising, so the paper should plot time against rules generated.
- **Known deviation.** Without A, the hashed path is no faster than traversal for verification at n ≤ 1600, or for deletion at n ≤ 600. There, constraint subjects cover almost all 625 e_min, so intersecting with them saves little.

E5–E7 notes: E5 measures coverage (what a policy can stop if the agent complies), not agent behaviour. E6 intents are oracle intents from AgentDojo's reference solutions; AgentDojo's prompt-based `local` provider produced no parsable tool calls with this model, so runs use native tool calling (superseded runs kept as `results/superseded_e6_*`). E7: a multiply-only hash clustered the per-pair keys (497 ns per lookup); all structures now use the MurmurHash3 finalizer. Calls from a pod to itself (859,126) are dropped from the E7 queries, as neither system has a rule for them.
