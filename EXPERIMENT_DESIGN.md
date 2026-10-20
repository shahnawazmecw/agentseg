# Experiment design (draft 1, 19 October 2026; all experiments run by 20 October 2026, see agentseg/README.md)

Target: IEEE Transactions on Computers, regular paper (10–12 pages, ≤45 references). Base papers: IMS (TDSC 2025) and TrustAgentNet (TCCN 2026), see `README.md`. Data: `datasets/`, see `DATASETS.md`.

## 1. What the paper claims

Working name: **AgentSeg**, an agent-aware, intent-driven micro-segmentation runtime for edge–cloud microservices.

1. **Agents as endpoints.** IMS's endpoint-group algebra is extended so an endpoint can be a pod *or* an AI agent, and an agent's groups come from its *verified* capabilities (a TrustAgentNet-style skill check), not from labels it declares itself. Intents cover both service-to-service traffic (L3/L4) and agent-to-tool calls (L7: tool name + parameter scope).
2. **Incremental at production scale.** Composition, reachability verification, compilation and dynamicity handling stay incremental at real-cluster scale (tens of thousands of microservices, hundreds of thousands of pods), where IMS was tested on 1,000 synthetic endpoints.
3. **Cheap per decision.** Enforcement cost per packet-flow or per tool call is small enough for the data path (target: µs-scale per decision on one core) and scales across cores.

TC fit: this is a runtime/systems contribution (scope items "operating systems, software systems, cloud computing", "performance… security… scalability", "workload characterization"). Detection accuracy is reported, but the headline numbers are latency, throughput, memory and scalability.

## 2. What the data looks like (measured 19 Oct 2026)

| Dataset | Measured facts | Used for |
|---|---|---|
| D2 Alibaba v2022, `CallGraph_0` (first 3 min) | 13.3 M call rows; 85,164 services; 17,691 microservices; 386,895 pods; 58,587 distinct microservice→microservice edges. Call types: mc 5.68 M, rpc 3.57 M, http 2.81 M, db 0.97 M, mq 0.20 M | Scale and churn (E1, E2) |
| D2, 40 files | 2 hours in 3-minute windows; pods appear and disappear across windows | Endpoint dynamicity (E2) |
| D1 Misuse Detection in Containers | 3,231,475 flows; 4,288 IPs; 20,830 distinct (src, dst, dport). Label 0 (benign) 2,953,291; attack labels 1–11 from 34 (label 9) to 156,614 (label 2) flows | East-west enforcement (E3) |
| D3 LANL | 8 auth parts, flows, DNS, red-team ground truth (needs `pyarrow` to read) | Lateral movement, blast radius (E4) |
| D4 MSB | 2,000 cases; 12 attack types; tasks × attack goals | Agent tool-call enforcement (E5) |
| D5 InjecAgent | 38 toolkits, 330 tools; 17 user cases, 62 attacker cases | Agent tool-call enforcement (E5) |
| D6 AgentDojo | Task suites with injection tasks | End-to-end agent utility vs security (E6) |

Several D1 attack classes have under 200 flows, so D1 is used to test enforcement (blocked or not), not to train a classifier.

## 3. Experiments

Every timing: 10 runs, mean ± std (as IMS does), plus p50/p95/p99 for per-event latencies. Report the hardware exactly.

### E1. Scalability of compose / verify / compile (extends IMS Figs. 10, 11, 14)
- **Workload:** least-privilege intents derived from D2: allow each observed microservice→microservice edge, grouped by service; reachability queries sampled from observed traces (must be allowed) and from never-observed pairs (must be denied).
- **Sweep:** 1k → 5k → 10k → 17.7k microservices (sub-graphs by service), and the matching pod counts up to ~387k.
- **Metrics:** time per stage, peak memory, rules generated, rules per second.
- **Baselines:** IMS re-implemented (Python, as in the paper) at its own scale (2,000 intents, 1,000 EPs) to check the re-implementation against its published numbers, then at D2 scale; Kano-style verification if its code is available; brute-force matrix verification as a lower bound.

### E2. Endpoint and policy dynamicity (extends IMS Table VII, 5.05 ms at 1,000 EPs)
- **Workload:** replay pod births and deaths between consecutive 3-minute windows of D2 (40 windows); random label changes as in IMS for direct comparison; agent skill revocation events (from E5's agent set).
- **Metrics:** per-event processing latency (p50/p99), rules removed and added per event, full recompile vs incremental speed-up.

### E3. East-west enforcement efficacy (D1)
- **Method:** derive the allow-list from the benign flows in a training time window; enforce on later flows.
- **Metrics:** per-attack-label share of flows blocked; benign flows wrongly blocked; time to detect a new endpoint.
- **Baselines:** allow-all (no segmentation); namespace-level segmentation (coarse); IMS (labels without the agent extension).

### E4. Lateral-movement containment (D3 LANL)
- **Method:** build host groups from authentication history; segment; replay the red-team events.
- **Metrics:** red-team auth events that would be denied; legitimate auths denied; blast radius (hosts reachable from each compromised host) before vs after.

### E5. Agent tool-call enforcement, offline replay (D4 + D5)
- **Method:** each case's attempted tool call (tool, parameters, target) is checked by AgentSeg's L7 policy. No LLM is needed, so it is deterministic and repeatable.
- **Metrics:** attack calls blocked per attack type; benign calls blocked; per-call decision latency; throughput (decisions/s) on 1, 2, 4, 6 cores.
- **Baselines:** no guard; Open Policy Agent (Rego) with an equivalent policy (widely used, open source); TrustAgentNet-style "verify once at registration" without runtime checks.

### E6. End-to-end agent run (D6 AgentDojo, smaller)
- **Method:** AgentDojo suites with and without AgentSeg in the tool-call path.
- **Metrics:** utility (benign task success), attack success rate, added latency per task.
- **Needs an LLM**, see Section 5.

### E7. Micro-benchmarks and ablations (TC reviewers expect these)
- Per-decision latency of the lookup structure (hash vs bitset vs trie), cache behaviour, memory per rule.
- Ablations: IMS's optimizations A and B, the incremental path, verified vs declared agent groups.

## 4. Planned figures and tables (12-page budget)

Figures (8): architecture; E1 time vs size (stages); E1 memory; E2 per-event latency CDF; E3 per-attack block rate; E4 blast radius before/after; E5 decision latency and multi-core throughput; E6 utility vs attack success.
Tables (4): related work and features compared (IMS, Kano, TrustAgentNet, eZTrust, Cilium, OPA); dataset summary (Section 2); E5 per-attack-type results; ablation.

## 5. Decisions (made 19 October 2026)

1. **LLM for E6: small local model on the laptop CPU.** Use a ~1.5–3B instruction model with tool calling, 4-bit quantized (~1–2 GB RAM), served locally (Ollama or llama.cpp). Run a subset of AgentDojo suites. State in the paper that absolute utility is low for a small model and that the claim is the *difference* with and without AgentSeg; E5 (offline replay) carries the main agent result.
2. **Language: Python + Rust hot path.** Python for intents, algebra, composition, verification and compilation (directly comparable with IMS's Python prototype). Rust (exposed to Python via PyO3) for the per-decision lookup used in E5 and E7.
3. **Hardware: this laptop only.** AMD Ryzen 5 7530U (6 cores / 12 threads), 15.4 GB RAM, integrated GPU, Windows 11. E1 tops out at one D2 window (~17.7k microservices, ~387k pods); multi-core scaling goes to 6 cores / 12 threads. Report this as an edge-class machine; IMS used a Core i7 2.6 GHz with 16 GB, so the hardware is comparable.

## 6. Setup still to do

- `pip install pyarrow` (to read LANL parquet).
- Install Rust (rustup) and `maturin` for the PyO3 extension; install Ollama or llama.cpp and pull one small tool-calling model for E6. Neither is installed yet.
- Unpack D2 call graphs one window at a time; one 3-minute window is 13.3 M rows, so stream it rather than loading it whole (the laptop has ~2 GB free RAM with other programs open).
