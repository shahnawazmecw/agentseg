"""E4: lateral-movement containment on the LANL authentication log with red-team ground truth.

A default-deny policy is learned from the network authentications of the first L hours, all
before the first red-team event (150,885 s = 41.9 h). Policy keys, from finest to coarsest:
  user_pair (user, source computer, destination computer)
  pair      (source computer, destination computer)
  user_dst  (user, destination computer)
  dst       (destination computer: any source may authenticate to it)
Measured: the share of the 749 red-team authentications each policy denies; the share of later
legitimate network authentications it denies (all events after L whose key was first seen
after L, over the rest of the 58 days); and the blast radius of each red-team source computer
(computers reachable through allowed pairs, directly and transitively).
Input: ../datasets/derived/lanl_agg (e4/prep_lanl.py). Writes results/e4.json, results/e4_summary.md.
"""
import collections
import glob
import json
import os

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGG = os.path.join(HERE, "..", "datasets", "derived", "lanl_agg")
REDTEAM = os.path.join(HERE, "..", "datasets", "D3_lanl_sample", "redteam", "part-00000.parquet")
OUT = os.path.join(HERE, "results", "e4.json")
SUMMARY = os.path.join(HERE, "results", "e4_summary.md")
LEARN_H = (6, 12, 24, 41)
COLS = {"pair": ["src_computer", "dst_computer"], "user_dst": ["src_user", "dst_computer"],
        "user_pair": ["src_user", "src_computer", "dst_computer"]}


def load(kind):
    parts = [pq.read_table(p) for p in sorted(glob.glob(os.path.join(AGG, f"part-?????_{kind}.parquet")))]
    t = pa.concat_tables(parts)
    cols = COLS[kind]
    g = t.group_by(cols).aggregate([("first", "min"), ("count", "sum")]).rename_columns(cols + ["first", "count"])
    keys = list(zip(*(g[c].to_pylist() for c in cols)))
    return dict(zip(keys, zip(g["first"].to_pylist(), g["count"].to_pylist())))


AUTH0 = os.path.join(HERE, "..", "datasets", "D3_lanl_sample", "auth", "part-00000.parquet")  # hours 0-212, time-ordered
DAY = 86400


def next_day(cut, tables):
    """Share of legitimate network authentications in [cut, cut + 24 h) whose key was not seen before cut."""
    f = pq.ParquetFile(AUTH0)
    batches = []
    for rg in range(f.metadata.num_row_groups):
        tm = pc.cast(f.read_row_group(rg, columns=["time"])["time"], pa.int64())
        if pc.max(tm).as_py() < cut:
            continue
        if pc.min(tm).as_py() >= cut + DAY:
            break
        t = f.read_row_group(rg, columns=["time", "src_user", "src_computer", "dst_computer"])
        t = t.set_column(0, "time", tm)
        m = pc.and_(pc.and_(pc.greater_equal(tm, cut), pc.less(tm, cut + DAY)),
                    pc.and_(pc.not_equal(t["src_computer"], t["dst_computer"]),
                            pc.and_(pc.not_equal(t["src_computer"], "?"), pc.not_equal(t["dst_computer"], "?"))))
        batches.append(t.filter(m))
    ev = pa.concat_tables(batches)
    out = {"events": ev.num_rows}
    for kind, tab in tables.items():
        cols = COLS.get(kind, ["dst_computer"])
        keys = list(tab)
        kt = pa.table({**{c: [k[i] for k in keys] for i, c in enumerate(cols)}, "first": [tab[k][0] for k in keys]})
        j = ev.select(cols).join(kt, keys=cols, join_type="left outer")
        out[kind] = pc.sum(pc.greater_equal(j["first"], cut)).as_py() / ev.num_rows
    return out


def reach(adj, s):
    seen, todo = {s}, [s]
    while todo:
        x = todo.pop()
        for y in adj.get(x, ()):
            if y not in seen:
                seen.add(y)
                todo.append(y)
    return len(seen) - 1


def main():
    hours = sum(np.load(p) for p in glob.glob(os.path.join(AGG, "part-*_hours.npy")))
    rt = pq.read_table(REDTEAM).to_pylist()
    for r in rt:
        r["time"] = int(r["time"])
    first_rt = min(r["time"] for r in rt)
    tables = {k: load(k) for k in COLS}
    dst = {}
    for (s, d), (f, n) in tables["pair"].items():
        a = dst.get(d)
        dst[d] = (min(f, a[0]), n + a[1]) if a else (f, n)
    tables["dst"] = {(d,): v for d, v in dst.items()}
    rt_keys = {"user_pair": lambda r: (r["user"], r["src_computer"], r["dst_computer"]),
               "pair": lambda r: (r["src_computer"], r["dst_computer"]),
               "user_dst": lambda r: (r["user"], r["dst_computer"]), "dst": lambda r: (r["dst_computer"],)}
    computers = {c for k in tables["pair"] for c in k}
    res = {"network_auth_events": int(hours.sum()), "computers": len(computers), "redteam_events": len(rt),
           "redteam_sources": sorted({r["src_computer"] for r in rt}), "first_redteam_s": first_rt,
           "distinct_keys": {k: len(v) for k, v in tables.items()}, "learn": []}
    for L in LEARN_H:
        cut = L * 3600
        assert cut < first_rt
        test_events = int(hours[L:].sum())
        row = {"hours": L, "test_events": test_events, "kinds": {}}
        for kind, tab in tables.items():
            learned = {k for k, (f, _) in tab.items() if f < cut}
            denied_legit = sum(n for k, (f, n) in tab.items() if f >= cut)
            keyf = rt_keys[kind]
            rt_denied = sum(1 for r in rt if keyf(r) not in learned)
            row["kinds"][kind] = {"policy_keys": len(learned), "legit_denied_events": denied_legit,
                                  "legit_denied_share": denied_legit / test_events, "redteam_denied": rt_denied}
        row["next_24h"] = next_day(cut, tables)
        adj = collections.defaultdict(set)
        for (s, d), (f, _) in tables["pair"].items():
            if f < cut:
                adj[s].add(d)
        row["blast_radius"] = {s: {"direct": len(adj.get(s, ())), "transitive": reach(adj, s)} for s in res["redteam_sources"]}
        rt_dsts = collections.defaultdict(set)
        for r in rt:
            rt_dsts[r["src_computer"]].add(r["dst_computer"])
        row["redteam_targets_reachable"] = {s: sum(1 for d in ds if d in adj.get(s, ())) for s, ds in rt_dsts.items()}
        row["redteam_targets"] = {s: len(ds) for s, ds in rt_dsts.items()}
        res["learn"].append(row)
        print(L, "h:", {k: (v["redteam_denied"], round(100 * v["legit_denied_share"], 2)) for k, v in row["kinds"].items()}, flush=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    summarize(res)


def summarize(res):
    kinds = ("user_pair", "pair", "user_dst", "dst")
    L = ["# E4: lateral-movement containment (LANL, 58 days)", "",
         f"{res['network_auth_events']:,} network authentications among {res['computers']:,} computers; "
         f"{res['redteam_events']} red-team authentications from {len(res['redteam_sources'])} source computers, "
         f"the first at {res['first_redteam_s']:,} s ({res['first_redteam_s'] / 3600:.1f} h).", "",
         "## Red-team authentications denied / legitimate later authentications denied", "",
         "| Learned over | " + " | ".join(kinds) + " |", "|---|" + "---|" * len(kinds)]
    for row in res["learn"]:
        cells = [f"{100 * row['kinds'][k]['redteam_denied'] / res['redteam_events']:.1f}% / "
                 f"{100 * row['kinds'][k]['legit_denied_share']:.2f}%" for k in kinds]
        L.append(f"| first {row['hours']} h | " + " | ".join(cells) + " |")
    L += ["", "Legitimate denials are counted over all of the remaining days (a long horizon).", "",
          "## Legitimate authentications denied in the 24 h after learning", "",
          "| Learned over | Events | " + " | ".join(kinds) + " |", "|---|---|" + "---|" * len(kinds)]
    for row in res["learn"]:
        nd = row["next_24h"]
        L.append(f"| first {row['hours']} h | {nd['events']:,} | " + " | ".join(f"{100 * nd[k]:.2f}%" for k in kinds) + " |")
    L += ["",
          "## Blast radius of the red-team source computers (pair policy)", "",
          "| Learned over | Source | Direct | Transitive | Red-team targets | Targets directly allowed |", "|---|---|---|---|---|---|"]
    for row in res["learn"]:
        for s, b in row["blast_radius"].items():
            L.append(f"| {row['hours']} h | {s} | {b['direct']:,} | {b['transitive']:,} | {row['redteam_targets'][s]} | "
                     f"{row['redteam_targets_reachable'][s]} |")
    L += ["", f"Without segmentation every computer is reachable: {res['computers']:,}."]
    with open(SUMMARY, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
