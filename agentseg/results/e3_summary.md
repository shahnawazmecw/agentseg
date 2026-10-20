# E3: east-west enforcement (Misuse Detection in Containers)

2,953,291 benign flows over 83 capture hours (2023-03-19 15 to 2023-12-07 01).

## Attack flows blocked by a policy learned from all benign flows

| Label | Scenario | Flows | pair+port | pair | service | subnet |
|---|---|---|---|---|---|---|
| 1 | CVE-2020-13379 (Grafana SSRF) | 111,251 | 19.1% | 19.1% | 3.8% | 0.0% |
| 2 | Node-RED reconnaissance | 156,614 | 95.0% | 95.0% | 95.0% | 0.0% |
| 3 | Node-RED RCE | 168 | 5.4% | 3.0% | 3.0% | 3.0% |
| 4 | Node-RED container escape | 163 | 4.9% | 1.8% | 1.8% | 1.8% |
| 5 | CVE-2021-43798 (Grafana path traversal) | 36 | 27.8% | 27.8% | 2.8% | 0.0% |
| 6 | CVE-2019-20933 (InfluxDB auth bypass) | 193 | 34.7% | 34.7% | 8.8% | 8.8% |
| 7 | CVE-2021-30465 (runc) | 131 | 0.0% | 0.0% | 0.0% | 0.0% |
| 8 | CVE-2021-25741 (Kubernetes subpath) | 824 | 0.0% | 0.0% | 0.0% | 0.0% |
| 9 | CVE-2022-23648 (containerd) | 34 | 0.0% | 0.0% | 0.0% | 0.0% |
| 10 | CVE-2019-5736 (runc) | 48 | 0.0% | 0.0% | 0.0% | 0.0% |
| 11 | DeathStarBench Nuclei scan | 8,722 | 0.0% | 0.0% | 0.0% | 0.0% |
| all | | 278,184 | 61.2% | 61.2% | 55.1% | 0.0% |

Policy entries learned from all benign flows: pair+port 133, pair 87, service 109, subnet 87.

## False denials of later benign traffic (time split)

| Learned on first | Cut hour | pair+port | pair | service | subnet |
|---|---|---|---|---|---|
| 10% of benign flows | 2023-09-22 22 | 84.359% | 84.359% | 84.358% | 10.755% |
| 25% of benign flows | 2023-12-06 16 | 0.002% | 0.002% | 0.002% | 0.002% |
| 50% of benign flows | 2023-12-06 19 | 0.003% | 0.000% | 0.003% | 0.003% |
| 75% of benign flows | 2023-12-06 22 | 0.002% | 0.000% | 0.002% | 0.002% |
