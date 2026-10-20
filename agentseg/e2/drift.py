"""E2a: policy drift against learning-window length on Alibaba v2022 (3-minute windows).

The allow-list is the union of observed (caller, callee, rpctype) triples over windows
0..L-1. It is tested on each of the next 5 windows: share of distinct triples, and share of
calls, that it would deny. Writes results/e2_drift.jsonl and results/e2_drift_summary.md.
"""
import json
import os
import pickle
import statistics

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIVED = os.path.join(HERE, "..", "datasets", "derived", "alibaba_callgraph_w{}.pkl")
OUT = os.path.join(HERE, "results", "e2_drift.jsonl")
SUMMARY = os.path.join(HERE, "results", "e2_drift_summary.md")
LEARN = (1, 2, 5, 10, 20)
TEST_WINDOWS = 5


def triples(w):
    with open(DERIVED.format(w), "rb") as fh:
        d = pickle.load(fh)
    names = d["ms_names"]
    return {(names[a], names[b], R): calls for (a, b), rt in d["edges"].items() for R, calls in rt.items()}


def main():
    cache = {}

    def get(w):
        if w not in cache:
            cache[w] = triples(w)
        return cache[w]

    recs = []
    for L in LEARN:
        allowed = set()
        for w in range(L):
            allowed.update(get(w))
        for t in range(L, L + TEST_WINDOWS):
            test = get(t)
            new = [k for k in test if k not in allowed]
            rec = {"learn_windows": L, "learn_minutes": 3 * L, "test_window": t, "policy_triples": len(allowed),
                   "test_triples": len(test), "denied_triples": len(new),
                   "test_calls": sum(test.values()), "denied_calls": sum(test[k] for k in new)}
            recs.append(rec)
            print(rec, flush=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in recs)
    lines = ["# E2a: drift against learning window (Alibaba v2022, east-west)", "",
             "Mean ± std over the 5 test windows that follow the learning period.", "",
             "| Learning window | Policy triples | Denied triples | Denied calls |", "|---|---|---|---|"]
    for L in LEARN:
        rs = [r for r in recs if r["learn_windows"] == L]
        dt = [100 * r["denied_triples"] / r["test_triples"] for r in rs]
        dc = [100 * r["denied_calls"] / r["test_calls"] for r in rs]
        lines.append(f"| {3 * L} min | {rs[0]['policy_triples']:,} | {statistics.mean(dt):.2f}% ± {statistics.stdev(dt):.2f} "
                     f"| {statistics.mean(dc):.3f}% ± {statistics.stdev(dc):.3f} |")
    with open(SUMMARY, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
