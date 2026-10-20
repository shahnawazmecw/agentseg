# Datasets

Checked on 19 October 2026. All are free to download; licences are as stated on each page.

## Recommended set

| # | Role in the paper | Dataset | Licence | Size | Download |
|---|---|---|---|---|---|
| D1 | East-west traffic and attacks inside a Kubernetes microservice cluster (enforcement, lateral movement) | Misuse Detection in Containers Dataset (AINA 2024): network flows, benign plus 11 attack scenarios incl. container escape and CVE exploits | MIT | ~2 GB (`dataset.csv`) | https://www.kaggle.com/datasets/yigitsever/misuse-detection-in-containers-dataset |
| D2 | Large-scale service topology for policy-scaling experiments (IMS-style, up to ~20,000 microservices) | Alibaba cluster-trace-microservices-v2022: call graphs, per-instance resources, RPC metrics, 13 days | Not stated on the page; check the repo before use | ~4 GiB per hour of MSCallGraph (use a few hours) | https://github.com/alibaba/clusterdata/tree/master/cluster-trace-microservices-v2022 (`bash fetchData.sh start_date=0d0 end_date=1d0`) |
| D2-alt | Smaller topology with service placement (Kaggle alternative to D2) | Microservices Bottleneck Localization Dataset (DeathStarBench social network: RPC maps, placement, traces) | Apache 2.0 | ~68 GB total (meta-data folder is small) | https://www.kaggle.com/datasets/gagansomashekar/microservices-bottleneck-detection-dataset |
| D3 | Real lateral movement with ground truth (authentication graph, red-team events) | LANL Comprehensive, Multi-Source Cyber-Security Events | CC0 1.0 | ~12 GB (auth 7.2 GB, redteam 4.8 KB) | Official: https://csr.lanl.gov/data/cyber1/ · Kaggle parquet mirror: https://www.kaggle.com/datasets/omniaayman1/comprehensive-multi-source-cyber-security-events |
| D4 | Agent endpoints: tools, tasks and attacks against tool-using agents (TrustAgentNet-style skill verification) | MCP Security Bench (MSB): 405 tools, 65 tasks, 12 attack types, 2,000+ attack instances | MIT | 1.4 MB (+ GitHub pipeline) | https://huggingface.co/datasets/DongsenZhang/MSB · https://github.com/dongsenzhang/MSB |
| D5 | Indirect prompt-injection cases for tool calls | InjecAgent (Kaggle copy) | Apache 2.0 | 6 MB | https://www.kaggle.com/datasets/alexbenjaminwarner/injecagent |
| D6 | Agent task suites with injection tasks (runtime check) | AgentDojo | MIT | pip package | https://github.com/ethz-spylab/agentdojo (`pip install agentdojo`) |

## Checked and not recommended

- IEEE DataPort ZGG-RR Zero Trust Access (10.21227/tmxr-6b67), ONE-MS-I microservice traffic (10.21227/0h62-zy24), Kano network-policy YAML (10.21227/8fym-nx33): Standard datasets, need a paid DataPort subscription.
- Kubernetes Intrusion Detection Datasets (kaggle redamorsli/kube-ids0): licence "Unknown".
- CIC-IDS2017 / CSE-CIC-IDS2018 (Kaggle mirrors): perimeter (north-south) traffic and widely criticised labels; a weak fit for east-west micro-segmentation.
- Small "AI agent security 2026" Kaggle sets (<1 MB): synthetic, unclear provenance.
