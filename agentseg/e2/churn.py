"""E2b: replay real churn on Alibaba v2022 (minutes 30-75).

Policy: learned from windows 0-9 (30 min): one intent per observed (caller, callee, rpctype);
datastore callees (db, mc) get an ingress default-deny constraint admitting their learned callers.
Replay windows 10-24. In each 3-minute window:
  * policy events: triples not yet in the policy are added (learning mode). AgentSeg merges
    them incrementally (core.incremental) and refreshes the touched group rows; IMS recomposes
    all intents (its documented handling of intent addition).
  * pod events: pods born or dying in that window (MSMetrics lifetimes). AgentSeg updates the
    membership table. IMS Algorithm 6 needs the per-pair rule base, which does not fit at full
    scale (E1), so it is replayed on a service subset whose per-pair rules stay <= 5 M, with the
    same events applied to an AgentSeg table on that subset.
Writes results/e2_churn.jsonl and results/e2_churn_summary.md.
"""
import gc
import json
import os
import pickle
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from core.groups import GroupTable  # noqa: E402
from core.incremental import add_intents  # noqa: E402
from ims.compiler import add_ep, compile_intents, remove_ep  # noqa: E402
from ims.policy import compose  # noqa: E402

DERIVED = os.path.join(HERE, "..", "datasets", "derived")
OUT = os.path.join(HERE, "results", "e2_churn.jsonl")
SUMMARY = os.path.join(HERE, "results", "e2_churn_summary.md")
LEARN, LAST = 10, 24
WINDOW_MS = 180_000
DATASTORE_RPC = ("db", "mc")
SUBSET_MAX_RULES = 5_000_000
REPEATS = 3


def load(w):
    with open(os.path.join(DERIVED, f"alibaba_callgraph_w{w}.pkl"), "rb") as fh:
        d = pickle.load(fh)
    names = d["ms_names"]
    return d, {(names[a], names[b], R) for (a, b), rt in d["edges"].items() for R in rt}


class Ids:
    def __init__(self):
        self.ms = {}

    def __call__(self, name):
        i = self.ms.get(name)
        if i is None:
            i = self.ms[name] = len(self.ms) + 1  # 0 is Null
        return i


def raw(ids, trip):
    a, b, R = trip
    return (frozenset((ids(a),)), (R,), frozenset((ids(b),)))


def constraints_for(ids, learned):
    callers = {}
    for a, b, R in learned:
        if R in DATASTORE_RPC:
            callers.setdefault(b, {}).setdefault(R, set()).add(ids(a))
    return [(frozenset((ids(b),)), ([], False), ([(R, frozenset(s)) for R, s in sorted(rs.items())], True))
            for b, rs in sorted(callers.items())]


def timed(fn):
    gc.collect()
    gc.disable()
    t = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t
    gc.enable()
    return out, dt


def pod_events(life, lo, hi):
    """Births (first sample in [lo, hi)) and deaths (one minute after the last sample in [lo, hi))."""
    ev = []
    for name, (ms, first, last) in life.items():
        if lo <= first < hi and first > 0:
            ev.append((first, "add", name, ms))
        if lo <= last + 60_000 < hi:
            ev.append((last + 60_000, "remove", name, ms))
    ev.sort()
    return ev


def alive(life, t):
    return {name: ms for name, (ms, first, last) in life.items() if first <= t <= last}


def replay(rep, life, windows, out):
    ids = Ids()
    learned = set()
    for w in range(LEARN):
        learned |= windows[w]
    C_raw = constraints_for(ids, learned)
    intents_raw = [raw(ids, t) for t in sorted(learned)]
    I, C = compose(intents_raw, C_raw)
    t0 = LEARN * WINDOW_MS
    pods = alive(life, t0)
    pid = {name: i for i, name in enumerate(sorted(life))}
    gt = GroupTable(I, {pid[p]: ids(ms) for p, ms in pods.items()})
    for w in range(LEARN, LAST + 1):
        new = sorted(windows[w] - learned)
        new_raw = [raw(ids, t) for t in new]
        touched = {next(iter(r[0])) for r in new_raw}

        def agentseg_add():
            kept = add_intents(I, C, new_raw)
            gt.refresh(I, touched)
            return kept

        kept, t_inc = timed(agentseg_add)
        learned.update(new)
        intents_raw.extend(new_raw)
        _, t_full = timed(lambda: compose(intents_raw, C_raw))
        ev = pod_events(life, w * WINDOW_MS, (w + 1) * WINDOW_MS)

        def apply_pods():
            for _, kind, name, ms in ev:
                if kind == "add":
                    gt.relabel(pid[name], ids(ms))
                else:
                    gt.remove(pid[name])

        _, t_pods = timed(apply_pods)
        rec = {"part": "full", "repeat": rep, "window": w, "new_triples": len(new), "admitted_triples": kept,
               "agentseg_incremental_s": t_inc, "ims_recompose_s": t_full, "policy_triples": len(learned),
               "pod_events": len(ev), "agentseg_pod_events_s": t_pods, "members": len(gt.member)}
        out(rec)


def pick_subset(life, windows, seed=0):
    """Services ordered by the pod events of their microservices during the replay (most first,
    random tie-break), kept while the per-pair rule count at minute 30 stays under the cap."""
    with open(os.path.join(DERIVED, "alibaba_callgraph_w0.pkl"), "rb") as fh:
        d0 = pickle.load(fh)
    names = d0["ms_names"]
    learned = set().union(*(windows[w] for w in range(LEARN)))
    pods_at = {}
    for p, ms in alive(life, LEARN * WINDOW_MS).items():
        pods_at[ms] = pods_at.get(ms, 0) + 1
    churn = {}
    for _, _, _, ms in pod_events(life, LEARN * WINDOW_MS, (LAST + 1) * WINDOW_MS):
        churn[ms] = churn.get(ms, 0) + 1
    rng = random.Random(seed)
    services = sorted(d0["services"])
    rng.shuffle(services)
    services.sort(key=lambda s: -sum(churn.get(names[m], 0) for m in d0["services"][s]))
    sel = set()
    for s in services:
        cand = sel | {names[m] for m in d0["services"][s]}
        rules = sum(pods_at.get(a, 0) * pods_at.get(b, 0) for a, b, _ in learned if a in cand and b in cand)
        if rules <= SUBSET_MAX_RULES:
            sel = cand
        if len(sel) >= 200:
            break
    return sel


def replay_subset(rep, life, windows, sel, out):
    ids = Ids()
    learned = {t for w in range(LEARN) for t in windows[w] if t[0] in sel and t[1] in sel}
    I, _ = compose([raw(ids, t) for t in sorted(learned)], constraints_for(ids, learned))
    t0 = LEARN * WINDOW_MS
    pid = {name: i for i, name in enumerate(sorted(life))}
    eps = {pid[p]: ids(ms) for p, ms in alive(life, t0).items() if ms in sel}
    (ft, groups), t_compile = timed(lambda: compile_intents(I, dict(eps)))
    gt = GroupTable(I, eps)
    ims_eps = dict(eps)
    ev = [e for e in pod_events(life, t0, (LAST + 1) * WINDOW_MS) if e[3] in sel]
    ims_t, ims_rules, seg_t = [], [], []
    gc.collect()
    gc.disable()
    for _, kind, name, ms in ev:
        p = pid[name]
        if kind == "add":
            if p in ims_eps:
                continue
            t = time.perf_counter()
            n = add_ep(ft, groups, I, ims_eps, p, ids(ms))
            ims_t.append(time.perf_counter() - t)
            t = time.perf_counter()
            gt.relabel(p, ids(ms))
            seg_t.append(time.perf_counter() - t)
        else:
            if p not in ims_eps:
                continue
            t = time.perf_counter()
            n = remove_ep(ft, groups, ims_eps, p)
            ims_t.append(time.perf_counter() - t)
            t = time.perf_counter()
            gt.remove(p)
            seg_t.append(time.perf_counter() - t)
        ims_rules.append(n)
    gc.enable()
    q = lambda v, f: sorted(v)[min(len(v) - 1, int(f * len(v)))] if v else None  # noqa: E731
    out({"part": "subset", "repeat": rep, "microservices": len(sel), "pods_at_start": len(eps),
         "per_pair_rules_at_start": ft.n_rules + 0, "ims_initial_compile_s": t_compile, "events": len(ims_t),
         "ims_event_ms_mean": 1e3 * statistics.mean(ims_t) if ims_t else None,
         "ims_event_ms_p99": 1e3 * q(ims_t, 0.99) if ims_t else None,
         "ims_rules_touched_mean": statistics.mean(ims_rules) if ims_rules else None,
         "agentseg_event_us_mean": 1e6 * statistics.mean(seg_t) if seg_t else None,
         "agentseg_event_us_p99": 1e6 * q(seg_t, 0.99) if seg_t else None})


def main():
    with open(os.path.join(DERIVED, "alibaba_pod_lifecycle.pkl"), "rb") as fh:
        life = pickle.load(fh)["pods"]
    windows = {w: load(w)[1] for w in range(LAST + 1)}
    recs = []

    def out(r):
        recs.append(r)
        print(r, flush=True)

    sel = pick_subset(life, windows)
    for rep in range(REPEATS):
        replay(rep, life, windows, out)
        replay_subset(rep, life, windows, sel, out)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in recs)
    summarize(recs)


def summarize(recs):
    full = [r for r in recs if r["part"] == "full"]
    sub = [r for r in recs if r["part"] == "subset"]
    m = lambda v: f"{statistics.mean(v):.2f} ± {statistics.stdev(v):.2f}" if len(v) > 1 else f"{v[0]:.2f}"  # noqa: E731
    lines = ["# E2b: churn replay on Alibaba v2022 (minutes 30–75)", "",
             f"Policy learned from minutes 0–30; {REPEATS} repeats of the replay; laptop, one thread, GC off during timing.", "",
             "## Policy events, full scale (per 3-minute window)", "",
             "| Window | New triples | Admitted | AgentSeg incremental (ms) | IMS recompose (ms) | Speed-up |",
             "|---|---|---|---|---|---|"]
    for w in sorted({r["window"] for r in full}):
        rs = [r for r in full if r["window"] == w]
        inc = [1e3 * r["agentseg_incremental_s"] for r in rs]
        rec = [1e3 * r["ims_recompose_s"] for r in rs]
        lines.append(f"| {w} | {rs[0]['new_triples']:,} | {rs[0]['admitted_triples']:,} | {m(inc)} | {m(rec)} | "
                     f"{statistics.mean(rec) / statistics.mean(inc):.0f}x |")
    ev = sum(r["pod_events"] for r in full if r["repeat"] == 0)
    tp = sum(r["agentseg_pod_events_s"] for r in full if r["repeat"] == 0)
    lines += ["", f"Pod events, full scale: {ev:,} births and deaths over 45 minutes; AgentSeg membership updates "
              f"{1e6 * tp / max(ev, 1):.2f} µs per event on average (batch time / events, repeat 0).", "",
              "## Pod events, subset where IMS per-pair rules fit", ""]
    if sub and sub[0]["events"]:
        s = sub[0]
        lines += [f"{s['microservices']} microservices, {s['pods_at_start']:,} pods, {s['per_pair_rules_at_start']:,} "
                  f"per-pair rules at minute 30; {s['events']} pod events replayed.", "",
                  "| | Mean | p99 |", "|---|---|---|",
                  f"| IMS Algorithm 6 (ms) | {m([r['ims_event_ms_mean'] for r in sub])} | {m([r['ims_event_ms_p99'] for r in sub])} |",
                  f"| AgentSeg membership (µs) | {m([r['agentseg_event_us_mean'] for r in sub])} | "
                  f"{m([r['agentseg_event_us_p99'] for r in sub])} |", "",
                  f"IMS rewrites {statistics.mean(r['ims_rules_touched_mean'] for r in sub):,.0f} flow rules per event on average."]
    with open(SUMMARY, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
