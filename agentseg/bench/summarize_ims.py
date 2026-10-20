"""Summarise results/ims_repro.jsonl into results/ims_repro_summary.md (mean ± std per point,
and slowdown of each optimization setting relative to (A, B) at the largest size, as in IMS
Tables III–VI)."""
import collections
import json
import os
import statistics

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "results", "ims_repro.jsonl")
DST = os.path.join(HERE, "results", "ims_repro_summary.md")
NAMES = {(False, False): "(!A, !B)", (False, True): "(!A, B)", (True, False): "(A, !B)", (True, True): "(A, B)"}
TITLES = {"compose": "Constraint-based intent composition (IMS Fig. 10, Table III)",
          "verify": "Policy-level reachability verification (IMS Fig. 11, Table IV)",
          "delete": "Intent deletion (IMS Fig. 12, Table V)",
          "add": "Constraint addition, maintain original (IMS Fig. 13, Table VI)",
          "compile": "Intent compilation, 1000 EPs (IMS Fig. 14)"}


def main():
    pts = collections.defaultdict(list)
    extra = {}
    ep = None
    for line in open(SRC, encoding="utf-8"):
        r = json.loads(line)
        if r["exp"] == "epdyn":
            ep = r
            continue
        k = (r["exp"], r["A"], r["B"], r["n"])
        pts[k].append(r["seconds"])
        if "flow_rules" in r:
            extra[k] = r["flow_rules"]
    out = ["# IMS re-implementation: reproduction of the TDSC 2025 evaluation", "",
           "Seconds, mean ± std over runs (runs in brackets). Hardware: AMD Ryzen 5 7530U, 15.4 GB RAM, "
           "Windows 11, Python 3.12, single thread. IMS used a Core i7 2.6 GHz, 16 GB.", ""]
    for exp, title in TITLES.items():
        sizes = sorted({k[3] for k in pts if k[0] == exp})
        combos = [c for c in NAMES if any((exp, *c, n) in pts for n in sizes)]
        out += [f"## {title}", "", "| n | " + " | ".join(NAMES[c] for c in combos) + (" | flow rules |" if exp == "compile" else " |"),
                "|---|" + "---|" * (len(combos) + (exp == "compile"))]
        for n in sizes:
            cells = []
            for c in combos:
                v = pts.get((exp, *c, n), [])
                sd = statistics.stdev(v) if len(v) > 1 else 0.0
                cells.append(f"{statistics.mean(v):.3f} ± {sd:.3f} ({len(v)})" if v else "–")
            row = f"| {n} | " + " | ".join(cells)
            out.append(row + (f" | {extra[(exp, True, True, n)]:,} |" if exp == "compile" else " |"))
        if len(combos) == 4:
            n = sizes[-1]
            base = statistics.mean(pts[(exp, True, True, n)])
            ratios = ", ".join(f"{NAMES[c]} {statistics.mean(pts[(exp, *c, n)]) / base:.1f}x" for c in combos)
            out += ["", f"Slowdown relative to (A, B) at n = {n}: {ratios}."]
        out.append("")
    if ep:
        out += ["## EP dynamicity (IMS Table VII)", "",
                f"{ep['eps']} EPs, each relabelled {ep['reps']} times, (A, B): "
                f"{ep['ms_mean']:.2f} ± {ep['ms_std']:.2f} ms per EP; "
                f"rules removed {ep['rules_removed_mean']:.0f}, added {ep['rules_added_mean']:.0f} per update; "
                f"{ep['initial_flow_rules']:,} rules before updates. IMS reports about 5.05 ms with about 6000 rules "
                "removed and 6000 added.", ""]
    with open(DST, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
