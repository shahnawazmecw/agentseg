"""E3: east-west enforcement on the Misuse Detection in Containers dataset (Kubernetes flows,
benign + 11 attack labels).

An allow-list is learned from benign flows and enforced default-deny. Four policy granularities,
from least privilege to coarse:
  pair+port    (src IP, dst IP, dst port, protocol)   per-endpoint-pair least privilege
  pair         (src IP, dst IP, protocol)             any port between an allowed pair
  service      (dst IP, dst port, protocol)           any caller may reach an allowed service port
  subnet       (src /16, dst /16, dst port, protocol) namespace-like segments
The dataset has IPs but no pod metadata, so an endpoint is an IP; at this granularity group
rules and per-pair rules coincide, and E3 measures what segmentation blocks, not its cost.

Two learning settings:
  * all benign: the policy is learned from every benign flow (the most permissive policy one
    could learn); attack flows are then denied only if their key never occurs in benign traffic.
  * time split: learned from the benign flows before the q-quantile of benign time, tested on the
    later benign flows (false denials). The attack captures mostly precede the benign capture, so
    attack blocking is reported for the all-benign policy and for each split policy.
Writes results/e3.json and results/e3_summary.md.
"""
import collections
import csv
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "..", "datasets", "D1_misuse_detection_containers", "dataset.csv")
OUT = os.path.join(HERE, "results", "e3.json")
SUMMARY = os.path.join(HERE, "results", "e3_summary.md")
LABELS = {"1": "CVE-2020-13379 (Grafana SSRF)", "2": "Node-RED reconnaissance", "3": "Node-RED RCE",
          "4": "Node-RED container escape", "5": "CVE-2021-43798 (Grafana path traversal)",
          "6": "CVE-2019-20933 (InfluxDB auth bypass)", "7": "CVE-2021-30465 (runc)",
          "8": "CVE-2021-25741 (Kubernetes subpath)", "9": "CVE-2022-23648 (containerd)",
          "10": "CVE-2019-5736 (runc)", "11": "DeathStarBench Nuclei scan"}
QUANTILES = (0.1, 0.25, 0.5, 0.75)


def keys(s, sp, d, p, pr):
    """Flows are first put in client -> service order: CICFlowMeter records some flows with the
    client's ephemeral port as the destination port (dst >= 32768 and src < 32768)."""
    if int(p) >= 32768 and int(sp) < 32768:
        s, d, sp, p = d, s, p, sp
    s16, d16 = ".".join(s.split(".")[:2]), ".".join(d.split(".")[:2])
    return {"pair+port": (s, d, p, pr), "pair": (s, d, pr), "service": (d, p, pr), "subnet": (s16, d16, p, pr)}


GRANS = ("pair+port", "pair", "service", "subnet")


def main():
    benign_by_day = {g: collections.defaultdict(collections.Counter) for g in GRANS}  # key -> day -> flows
    attack = {g: collections.defaultdict(collections.Counter) for g in GRANS}  # label -> key -> flows
    day_flows = collections.Counter()
    with open(SRC, newline="", encoding="utf-8", errors="replace") as fh:
        r = csv.reader(fh)
        h = next(r)
        i_s, i_sp, i_d, i_p, i_pr, i_t, i_l = (h.index(k) for k in ("Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp", "Label"))
        for row in r:
            ks = keys(row[i_s], row[i_sp], row[i_d], row[i_p], row[i_pr])
            lab = row[i_l]
            if lab == "0":
                day = row[i_t][:13]  # hour bucket, so the time-split cuts differ
                day_flows[day] += 1
                for g in GRANS:
                    benign_by_day[g][ks[g]][day] += 1
            else:
                for g in GRANS:
                    attack[g][lab][ks[g]] += 1
    days = sorted(day_flows)
    total = sum(day_flows.values())
    res = {"benign_flows": total, "benign_days": len(days), "first_day": days[0], "last_day": days[-1],
           "granularities": {}}
    for g in GRANS:
        allowed_all = set(benign_by_day[g])
        out = {"policy_entries_all_benign": len(allowed_all), "attacks_all_benign": {}, "splits": []}
        for lab, kc in sorted(attack[g].items(), key=lambda x: int(x[0])):
            flows = sum(kc.values())
            blocked = sum(n for k, n in kc.items() if k not in allowed_all)
            out["attacks_all_benign"][lab] = {"flows": flows, "blocked_flows": blocked, "keys": len(kc),
                                              "blocked_keys": sum(1 for k in kc if k not in allowed_all)}
        for q in QUANTILES:
            cum, cut = 0, days[-1]
            for d in days:
                cum += day_flows[d]
                if cum >= q * total:
                    cut = d
                    break
            learned = {k for k, dc in benign_by_day[g].items() if any(d <= cut for d in dc)}
            test = sum(n for k, dc in benign_by_day[g].items() for d, n in dc.items() if d > cut)
            denied = sum(n for k, dc in benign_by_day[g].items() if k not in learned for d, n in dc.items() if d > cut)
            att = {lab: sum(n for k, n in kc.items() if k not in learned) / sum(kc.values()) for lab, kc in attack[g].items()}
            out["splits"].append({"quantile": q, "cut_day": cut, "policy_entries": len(learned), "test_benign_flows": test,
                                  "benign_denied_flows": denied, "attack_flows_blocked_share": att})
        res["granularities"][g] = out
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    summarize(res)


def summarize(res):
    L = ["# E3: east-west enforcement (Misuse Detection in Containers)", "",
         f"{res['benign_flows']:,} benign flows over {res['benign_days']} capture hours ({res['first_day']} to {res['last_day']}).", "",
         "## Attack flows blocked by a policy learned from all benign flows", "",
         "| Label | Scenario | Flows | " + " | ".join(GRANS) + " |", "|---|---|---|" + "---|" * len(GRANS)]
    g0 = res["granularities"]
    for lab in sorted(g0["pair+port"]["attacks_all_benign"], key=int):
        a = g0["pair+port"]["attacks_all_benign"][lab]
        cells = [f"{100 * g0[g]['attacks_all_benign'][lab]['blocked_flows'] / a['flows']:.1f}%" for g in GRANS]
        L.append(f"| {lab} | {LABELS[lab]} | {a['flows']:,} | " + " | ".join(cells) + " |")
    tot = {g: (sum(v["blocked_flows"] for v in g0[g]["attacks_all_benign"].values()),
               sum(v["flows"] for v in g0[g]["attacks_all_benign"].values())) for g in GRANS}
    L.append("| all | | " + f"{tot[GRANS[0]][1]:,} | " + " | ".join(f"{100 * b / n:.1f}%" for b, n in tot.values()) + " |")
    L += ["", "Policy entries learned from all benign flows: " +
          ", ".join(f"{g} {g0[g]['policy_entries_all_benign']:,}" for g in GRANS) + ".", "",
          "## False denials of later benign traffic (time split)", "",
          "| Learned on first | Cut hour | " + " | ".join(GRANS) + " |", "|---|---|" + "---|" * len(GRANS)]
    for i, q in enumerate(QUANTILES):
        cells = []
        for g in GRANS:
            s = g0[g]["splits"][i]
            cells.append(f"{100 * s['benign_denied_flows'] / max(s['test_benign_flows'], 1):.3f}%")
        L.append(f"| {int(100 * q)}% of benign flows | {g0['pair+port']['splits'][i]['cut_day']} | " + " | ".join(cells) + " |")
    with open(SUMMARY, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
