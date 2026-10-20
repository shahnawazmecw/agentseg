"""E1 supplement: measured per-pair (IMS) compilation at several sizes, to check the per-rule
cost model used to project the full topology.

Subsets: services in random order; a service is added only if the per-pair rule count stays
under the 5 M cap (so they avoid the microservices with thousands of pods). For each size:
compile time (3 runs, GC off), peak memory (tracemalloc), rules. Writes results/e1_pairwise.jsonl.
Usage: python e1/pairwise_points.py
"""
import gc
import json
import os
import random
import statistics
import sys
import time
import tracemalloc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from e1.run_e1 import load, workload  # noqa: E402
from ims.compiler import compile_intents  # noqa: E402
from ims.policy import compose  # noqa: E402

OUT = os.path.join(HERE, "results", "e1_pairwise.jsonl")
TARGETS = (100, 200, 400, 800, 1600)
CAP = 5_000_000


def capped_subset(w0, k, seed=1):
    pods = {m: len(p) for m, p in w0["pods"].items()}
    services = sorted(w0["services"])
    random.Random(seed).shuffle(services)
    sel, rules = set(), 0
    for s in services:
        cand = sel | set(w0["services"][s])
        r = sum(pods.get(a, 0) * pods.get(b, 0) * len(rt) for (a, b), rt in w0["edges"].items() if a in cand and b in cand)
        if r <= CAP:
            sel, rules = cand, r
        if len(sel) >= k:
            break
    return sel


def main():
    w0, w1 = load(0), load(1)
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["target"] for l in open(OUT)}
    for k in TARGETS:
        if k in done:
            continue
        sel = capped_subset(w0, k)
        _, intents, constraints, rqs, eps, pair_rules = workload(w0, w1, sel)
        I, _ = compose(intents, constraints)
        ts = []
        for _ in range(3):
            gc.collect()
            gc.disable()
            t = time.perf_counter()
            ft, _ = compile_intents(I, eps)
            ts.append(time.perf_counter() - t)
            gc.enable()
            n = ft.n_rules
            del ft
        gc.collect()
        tracemalloc.start()
        ft, _ = compile_intents(I, eps)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        del ft
        rec = {"target": k, "microservices": len(sel), "pods": len(eps), "rules": n, "seconds": statistics.mean(ts),
               "seconds_sd": statistics.stdev(ts), "peak_bytes": peak, "us_per_rule": 1e6 * statistics.mean(ts) / max(n, 1),
               "bytes_per_rule": peak / max(n, 1)}
        with open(OUT, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(rec, flush=True)


if __name__ == "__main__":
    main()
