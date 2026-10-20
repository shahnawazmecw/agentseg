"""Summarise results/e1.jsonl into results/e1_summary.md.

Per-pair (IMS) compilation is measured only where it fits (<= 5 M rules). Larger sizes are
projected from the measured per-rule time and bytes at the largest measured size, and are
marked as projections."""
import collections
import json
import os
import statistics

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, DST = os.path.join(HERE, "results", "e1.jsonl"), os.path.join(HERE, "results", "e1_summary.md")


def ms(v):
    return f"{1e3 * statistics.mean(v):.1f} ± {1e3 * statistics.stdev(v):.1f}" if len(v) > 1 else f"{1e3 * v[0]:.1f}"


def main():
    rows = collections.defaultdict(lambda: collections.defaultdict(list))
    info, order = {}, []
    for r in map(json.loads, open(SRC, encoding="utf-8")):
        k = r["k"]
        if r["stage"] == "info":
            info[k] = r
            order.append(k)
        else:
            rows[k][r["stage"]].append(r)
    order.sort(key=lambda k: info[k]["microservices"])
    per_rule_s = per_rule_b = None
    for k in order:
        pc = [r for r in rows[k]["pairwise_compile"] if "seconds" in r]
        pm = [r for r in rows[k]["pairwise_memory"] if "peak_bytes" in r]
        if pc and pm:
            n = pc[0]["rules"]
            per_rule_s = statistics.mean(r["seconds"] for r in pc) / n
            per_rule_b = pm[0]["peak_bytes"] / n
    out = ["# E1: IMS processing and compilation on the Alibaba v2022 east-west topology (window 0)", "",
           "Times in ms, mean ± std over runs (10 for policy stages and group compilation, 3 for per-pair "
           "compilation). Laptop: Ryzen 5 7530U, 15.4 GB RAM, Python 3.12, one thread, GC off during timing.", "",
           "| Microservices | Pods | Intents | Constraints | Compose | Verify (window-1 edges) | Drift | "
           "Group compile | Group rules | Group peak MB | Per-pair rules | Per-pair compile | Per-pair peak MB |",
           "|" + "---|" * 13]
    for k in order:
        i, s = info[k], rows[k]
        comp = [r["seconds"] for r in s["compose"]]
        ver = [r["seconds"] for r in s["verify"]]
        drift = s["verify"][0]["violations"] / s["verify"][0]["rq_triples"]
        gc_ = [r["seconds"] for r in s["group_compile"]]
        gmb = s["group_memory"][0]["peak_bytes"] / 2 ** 20
        pc = [r for r in s["pairwise_compile"] if "seconds" in r]
        pm = [r for r in s["pairwise_memory"] if "peak_bytes" in r]
        if pc:
            ptime = ms([r["seconds"] for r in pc])
            pmb = f"{pm[0]['peak_bytes'] / 2 ** 20:,.0f}" if pm else "–"
        elif per_rule_s:
            ptime = f"~{i['pairwise_rules'] * per_rule_s / 60:,.1f} min (projected)"
            pmb = f"~{i['pairwise_rules'] * per_rule_b / 2 ** 20:,.0f} (projected)"
        else:
            ptime = pmb = "–"
        out.append(f"| {i['microservices']:,} | {i['pods']:,} | {i['intents']:,} | {i['constraints']:,} | {ms(comp)} | "
                   f"{ms(ver)} | {100 * drift:.1f}% | {ms(gc_)} | {s['group_compile'][0]['rules']:,} | {gmb:,.1f} | "
                   f"{i['pairwise_rules']:,} | {ptime} | {pmb} |")
    if per_rule_s:
        out += ["", f"Per-pair compilation measured cost: {1e6 * per_rule_s:.2f} µs and {per_rule_b:.0f} bytes per rule "
                "(largest measured size); projections use these."]
    out += ["", "Drift = share of window-1 (next 3 minutes) relation triples that the window-0 policy does not allow."]
    with open(DST, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
