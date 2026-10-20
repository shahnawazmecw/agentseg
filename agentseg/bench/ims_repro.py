"""Reproduce the IMS evaluation (Ma et al., TDSC 2025, Sec. VII-B) with the re-implementation.

Each measured unit (experiment, optimization combo, size, run) is appended to a JSONL file as
soon as it finishes, so the script can be stopped and resumed: finished units are skipped.

Usage:  python bench/ims_repro.py [--deadline SECONDS] [--only compose,verify,...] [--runs 10]
"""
import argparse
import gc
import json
import os
import platform
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ims.compiler import compile_intents, update_ep  # noqa: E402
from ims.datasets import (GENERATOR, make_eps, make_forest, make_specs,  # noqa: E402
                          realize_constraints, realize_intents)
from ims.policy import (add_constraints, clone_constraints, clone_intents,  # noqa: E402
                        compose, delete_intents, verify)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "ims_repro.jsonl")
COMBOS = [(False, False), (False, True), (True, False), (True, True)]  # (A, B)
SIZES = {"compose": range(400, 2001, 400), "verify": range(400, 2001, 400),
         "delete": range(200, 1001, 200), "add": range(200, 1001, 200), "compile": range(200, 1001, 200)}

_cache = {}


def data(opt_a):
    if opt_a not in _cache:
        if "specs" not in _cache:
            _cache["specs"] = make_specs()
        ds1, ds2 = _cache["specs"]
        f, valid = make_forest(opt_a)
        _cache[opt_a] = {
            "valid": valid,
            "I1": realize_intents(f, ds1["intents"]), "C1": realize_constraints(f, ds1["constraints"]),
            "R1": realize_intents(f, ds1["rqs"]), "I2": realize_intents(f, ds2["intents"]),
            "C2": realize_constraints(f, ds2["constraints"]), "E2": [f.epg(s) for s in ds2["epgs"]],
        }
    return _cache[opt_a]


_state = {}


def cached(key, build):
    """Untimed set-up state, built once per key and copied for every run. Only the latest key
    is kept, to bound memory (units run grouped by experiment and combo)."""
    if key not in _state:
        _state.clear()
        _state[key] = build()
    I, C = _state[key]
    return clone_intents(I), clone_constraints(C)


def base_state(d, opt_a, hashed):
    """1000 intents + 1000 constraints from DS1 composed, then verified with 1000 RQs (Sec. VII-B)."""
    def build():
        I, C = compose(d["I1"][:1000], d["C1"][:1000], hashed)
        verify(I, C, d["R1"][:1000], hashed)
        return I, C
    return cached(("base", opt_a, hashed), build)


class timed:
    """perf_counter timing with the garbage collector off, as timeit does; otherwise full
    collections over millions of live sets dominate and add noise."""

    def __enter__(self):
        gc.collect()
        gc.disable()
        self.t = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.t
        gc.enable()


def unit(exp, opt_a, hashed, n):
    d = data(opt_a)
    if exp == "compose":
        with timed() as t:
            compose(d["I1"][:n], d["C1"][:n], hashed)
        return {"seconds": t.seconds}
    if exp == "verify":
        I, C = cached(("composed", opt_a, hashed, n), lambda: compose(d["I1"][:n], d["C1"][:n], hashed))
        with timed() as t:
            v = verify(I, C, d["R1"][:n], hashed)
        return {"seconds": t.seconds, "violations": v}
    if exp == "delete":
        I, _ = base_state(d, opt_a, hashed)
        with timed() as t:
            delete_intents(I, d["I2"][:n], d["E2"][:n // 10], hashed)
        return {"seconds": t.seconds}
    if exp == "add":
        I, C = base_state(d, opt_a, hashed)
        with timed() as t:
            add_constraints(I, C, d["C2"][:n], hashed)
        return {"seconds": t.seconds}
    if exp == "compile":
        I, _ = compose(d["I1"][:n], d["C1"][:n], hashed)
        eps = make_eps(d["valid"], 1000)
        with timed() as t:
            ft, _ = compile_intents(I, eps, hashed)
        return {"seconds": t.seconds, "flow_rules": ft.n_rules}
    raise ValueError(exp)


def ep_dynamicity(opt_a, hashed, reps=10, seed=0):
    """Table VII: relabel each of the 1000 EPs `reps` times; per-EP mean time, then mean/std over EPs."""
    d = data(opt_a)
    I, _ = compose(d["I1"][:1000], d["C1"][:1000], hashed)
    eps = make_eps(d["valid"], 1000)
    ft, groups = compile_intents(I, eps, hashed)
    initial = ft.n_rules
    rng, pool = random.Random(seed), sorted(d["valid"])
    per_ep, removed, added = [], [], []
    gc.collect()
    gc.disable()  # off for the whole loop; one collection per update would cost more than the update
    for a in sorted(eps):
        ts = []
        for _ in range(reps):
            new = rng.choice([e for e in pool if e != eps[a]])
            t = time.perf_counter()
            r, g = update_ep(ft, groups, I, eps, a, new)
            ts.append(time.perf_counter() - t)
            removed.append(r)
            added.append(g)
        per_ep.append(statistics.mean(ts))
    gc.enable()
    return {"ms_mean": 1e3 * statistics.mean(per_ep), "ms_std": 1e3 * statistics.stdev(per_ep),
            "rules_removed_mean": statistics.mean(removed), "rules_added_mean": statistics.mean(added),
            "initial_flow_rules": initial, "eps": len(eps), "reps": reps}


def done_keys():
    keys = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                keys.add((r["exp"], r["A"], r["B"], r.get("n"), r.get("run")))
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", type=float, default=540)
    ap.add_argument("--only", default="compose,verify,delete,add,compile,epdyn")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--combos", default="FF,FT,TF,TT", help="(A,B) settings to run, e.g. TF,TT")
    args = ap.parse_args()
    want = {(c[0] == "T", c[1] == "T") for c in args.combos.split(",")}
    stop_at = time.time() + args.deadline
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    meta = os.path.join(os.path.dirname(OUT), "ims_repro_meta.json")
    if not os.path.exists(meta):
        with open(meta, "w", encoding="utf-8") as fh:
            json.dump({"python": sys.version, "platform": platform.platform(),
                       "processor": platform.processor(), "generator": GENERATOR}, fh, indent=1)
    done = done_keys()
    todo = []
    for exp in args.only.split(","):
        if exp == "epdyn":
            todo += [("epdyn", a, b, None, None) for a, b in COMBOS if (a, b) == (True, True)]
            continue
        combos = [(True, True)] if exp == "compile" else COMBOS
        for a, b in combos:
            for n in SIZES[exp]:
                todo += [(exp, a, b, n, r) for r in range(args.runs)]
    todo = [k for k in todo if k not in done and (k[1], k[2]) in want]
    print(f"{len(done)} units done, {len(todo)} to go", flush=True)
    with open(OUT, "a", encoding="utf-8") as fh:
        for exp, a, b, n, r in todo:
            if time.time() > stop_at:
                print("deadline reached; rerun to resume", flush=True)
                return
            res = ep_dynamicity(a, b) if exp == "epdyn" else unit(exp, a, b, n)
            rec = {"exp": exp, "A": a, "B": b, "n": n, "run": r, **res}
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(rec, flush=True)
    print("all units done", flush=True)


if __name__ == "__main__":
    main()
