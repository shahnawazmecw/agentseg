# Downloaded datasets

Downloaded 19 October 2026. Sources and licences are listed in `../DATASETS.md`.

| Folder | Contents | Source |
|---|---|---|
| `D1_misuse_detection_containers/` | `dataset.csv`: Kubernetes microservice network flows, benign + 11 attack labels (MIT) | kaggle.com/datasets/yigitsever/misuse-detection-in-containers-dataset |
| `D2alt_deathstarbench_metadata/` | DeathStarBench social-network RPC maps (compose, home, user) and service-to-VM placement (Apache 2.0). Metadata only; the 68 GB traces were not downloaded | kaggle.com/datasets/gagansomashekar/microservices-bottleneck-detection-dataset |
| `D2_alibaba_microservices_v2022/` | First 2 hours (day 0, 00:00–02:00) of the v2022 trace, kept as `.tar.gz`: `CallGraph/` 40 files (3 min each), `MSMetrics/` 4 files (30 min each), `NodeMetrics/` 1 file. The call-rate table (MCRRTUpdate) was skipped. The repository has no LICENSE file; cite Luo et al., "The Power of Prediction: Microservice Auto Scaling via Workload Learning," SoCC 2022 | aliopentrace.oss-cn-beijing.aliyuncs.com/v2022MicroservicesTraces (via github.com/alibaba/clusterdata) |
| `D3_lanl_sample/` | LANL parquet files (CC0): `auth/` 8 parts, `flows/`, `dns/`, `redteam/` (ground truth). The process logs were skipped | kaggle.com/datasets/omniaayman1/comprehensive-multi-source-cyber-security-events |
| `D4_mcp_security_bench/` | `hf_data/`: MSB task, attack and case-manifest files; `msb_pipeline_github/`: the official evaluation pipeline with the 405 tool definitions (MIT) | huggingface.co/datasets/DongsenZhang/MSB, github.com/dongsenzhang/MSB |
| `D5_injecagent/` | InjecAgent test cases, attacker cases and tool definitions (Apache 2.0) | kaggle.com/datasets/alexbenjaminwarner/injecagent |
| `D6_agentdojo/` | AgentDojo source with the task suites in `src/agentdojo/default_suites/` (MIT) | github.com/ethz-spylab/agentdojo |

Not downloaded: Alibaba hours after 02:00 and its call-rate table, LANL process logs, and the DeathStarBench traces. Fetch more only if an experiment needs it.

The cloned repositories contain third-party code. Read it before running anything from them.
