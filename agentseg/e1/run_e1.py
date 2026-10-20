"""E1: IMS policy processing and compilation on the Alibaba v2022 east-west topology.

Least-privilege intents are derived from window 0: one intent per observed microservice ->
microservice edge, relations = the observed rpctypes. Datastore callees (receiving db or mc
calls) get an ingress constraint with default deny that admits only their observed callers.
Reachability queries are the edges of window 1, so verification also measures policy drift
(calls in the next 3 minutes that the window-0 policy does not allow).

Sizes are microservice subsets built by adding whole services in random order until the
target count is reached. Each unit is appended to results/e1.jsonl and skipped on rerun.

Usage: python e1/run_e1.py [--deadline SECONDS] [--runs 10]
"""
import argparse
import gc
import json
import os
import pickle
import random
import sys
import time
import tracemalloc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from core.groups import GroupTable  # noqa: E402
from ims.algebra import LabelForest  # noqa: E402
from ims.compiler import compile_intents  # noqa: E402
from ims.policy import compose, verify  # noqa: E402

DERIVED = os.path.join(HERE, "..", "datasets", "derived", "alibaba_callgraph_w{}.pkl")
OUT = os.path.join(HERE, "results", "e1.jsonl")
SIZES = (50, 100, 200, 400, 1000, 2000, 4000, 8000, None)  # None = all microservices in window 0
PAIRWISE_MAX_RULES = 5_000_000  # IMS per-EP-pair compilation is run only up to this many rules
DATASTORE_RPC = ("db", "mc")


def load(w):
    with open(DERIVED.format(w), "rb") as fh:
        return pickle.load(fh)


def subset(w0, k, seed=0):
    if k is None:
        return set(range(len(w0["ms_names"])))
    rng = random.Random(seed)
    services = sorted(w0["services"])
    rng.shuffle(services)
    sel = set()
    for s in services:
        sel.update(w0["services"][s])
        if len(sel) >= k:
            break
    return sel


def workload(w0, w1, sel):
    idx = {m: i + 1 for i, m in enumerate(sorted(sel))}  # value 0 is Null
    f = LabelForest(1, len(idx) + 1)
    one = lambda m: frozenset((idx[m],))  # noqa: E731
    intents, callers = [], {}
    for (a, b), rt in w0["edges"].items():
        if a in idx and b in idx:
            intents.append((one(a), tuple(sorted(rt)), one(b)))
            for R in rt:
                if R in DATASTORE_RPC:
                    callers.setdefault(b, {}).setdefault(R, set()).add(idx[a])
    constraints = [(one(b), ([], False), ([(R, frozenset(s)) for R, s in sorted(rs.items())], True))
                   for b, rs in callers.items()]
    # window 1 uses its own ids; map through names
    n0 = {name: i for i, name in enumerate(w0["ms_names"])}
    to0 = [n0.get(name) for name in w1["ms_names"]]
    rqs = []
    for (a, b), rt in w1["edges"].items():
        a0, b0 = to0[a], to0[b]
        if a0 in idx and b0 in idx:
            rqs.append((one(a0), tuple(sorted(rt)), one(b0)))
    eps = {}
    for m in sel:
        for p in w0["pods"].get(m, ()):
            eps[p] = idx[m]
    pair_rules = sum(len(w0["pods"].get(a, ())) * len(w0["pods"].get(b, ())) * len(rt)
                     for (a, b), rt in w0["edges"].items() if a in idx and b in idx)
    return f, intents, constraints, rqs, eps, pair_rules


def timed(fn):
    gc.collect()
    gc.disable()
    t = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t
    gc.enable()
    return out, dt


def peak_bytes(fn):
    gc.collect()
    tracemalloc.start()
    out = fn()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return out, peak


def done_keys():
    if not os.path.exists(OUT):
        return set()
    with open(OUT, encoding="utf-8") as fh:
        return {(r["k"], r["stage"], r["run"]) for r in map(json.loads, fh)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", type=float, default=480)
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()
    stop_at = time.time() + args.deadline
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    done = done_keys()
    w0, w1 = load(0), load(1)
    with open(OUT, "a", encoding="utf-8") as fh:
        def emit(rec):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(rec, flush=True)

        for k in SIZES:
            key_k = k if k is not None else "all"
            stages = [("info", 1), ("compose", args.runs), ("verify", args.runs), ("group_compile", args.runs),
                      ("group_memory", 1), ("pairwise_compile", 3), ("pairwise_memory", 1)]
            todo = [(s, r) for s, n in stages for r in range(n) if (key_k, s, r) not in done]
            if not todo:
                continue
            sel = subset(w0, k)
            f, intents, constraints, rqs, eps, pair_rules = workload(w0, w1, sel)
            for stage, r in todo:
                if time.time() > stop_at:
                    print("deadline reached; rerun to resume", flush=True)
                    return
                rec = {"k": key_k, "stage": stage, "run": r}
                if stage == "info":
                    rec.update(microservices=len(sel), pods=len(eps), intents=len(intents),
                               constraints=len(constraints), rqs=len(rqs), pairwise_rules=pair_rules)
                elif stage == "compose":
                    _, rec["seconds"] = timed(lambda: compose(intents, constraints))
                elif stage == "verify":
                    I, C = compose(intents, constraints)
                    v, rec["seconds"] = timed(lambda: verify(I, C, rqs, fix=False))
                    rec["violations"] = v
                    rec["rq_triples"] = sum(len(R) for _, R, _ in rqs)
                elif stage == "group_compile":
                    I, _ = compose(intents, constraints)
                    gt, rec["seconds"] = timed(lambda: GroupTable(I, eps))
                    rec["rules"] = gt.n_rules
                elif stage == "group_memory":
                    I, _ = compose(intents, constraints)
                    _, rec["peak_bytes"] = peak_bytes(lambda: GroupTable(I, eps))
                elif stage in ("pairwise_compile", "pairwise_memory"):
                    if pair_rules > PAIRWISE_MAX_RULES:
                        rec["skipped"] = f"{pair_rules:,} rules > {PAIRWISE_MAX_RULES:,}"
                    else:
                        I, _ = compose(intents, constraints)
                        if stage == "pairwise_compile":
                            (ft, _), rec["seconds"] = timed(lambda: compile_intents(I, eps))
                            rec["rules"] = ft.n_rules
                        else:
                            _, rec["peak_bytes"] = peak_bytes(lambda: compile_intents(I, eps))
                        gc.collect()
                emit(rec)
    print("all units done", flush=True)


if __name__ == "__main__":
    main()
