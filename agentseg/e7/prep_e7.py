"""E7 workload from Alibaba v2022 CallGraph window 0, written as little-endian uint32 arrays.

  member.u32      pod id -> microservice (group) id
  rules.u32       (src group, relation, dst group) triples of the least-privilege policy: every
                  observed microservice -> microservice edge with its rpctype (as in E1, where the
                  datastore constraints admit exactly the observed callers)
  queries.u32     (src pod, dst pod, relation) for the observed pod-to-pod calls, in trace order
                  (calls from a pod to itself are dropped: they never cross the network)
  random.u32      the same number of uniformly random (src pod, dst pod, relation) triples
  subset_*.u32    the same for the 50-microservice subset of E1, plus pairwise.u32: the per-pair
                  rules IMS would compile there (one per allowed pod pair and relation)
Usage: python e7/prep_e7.py
"""
import io
import json
import os
import pickle
import random
import sys
import tarfile

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from e1.run_e1 import subset  # noqa: E402

ROOT = os.path.join(HERE, "..", "datasets")
SRC = os.path.join(ROOT, "D2_alibaba_microservices_v2022", "CallGraph", "CallGraph_0.tar.gz")
OUT = os.path.join(ROOT, "derived", "e7")
RELS = {"rpc": 0, "http": 1, "mc": 2, "db": 3, "mq": 4, "UNKNOWN": 5}


def main():
    os.makedirs(OUT, exist_ok=True)
    ms, pod, member = {}, {}, []
    rules, q = set(), []
    self_calls = 0
    with tarfile.open(SRC, mode="r:gz") as tf:
        for m in tf:
            fh = io.TextIOWrapper(tf.extractfile(m), encoding="utf-8", errors="replace")
            next(fh)
            for line in fh:
                p = line.rstrip("\n").split(",")
                if len(p) != 11 or not (p[5].startswith("MS_") and p[8].startswith("MS_")):
                    continue
                a = ms.setdefault(p[5], len(ms))
                b = ms.setdefault(p[8], len(ms))
                r = RELS.get(p[4], 5)
                rules.add((a, r, b))
                if "_POD_" in p[6] and "_POD_" in p[9]:
                    ids = []
                    for inst, g in ((p[6], a), (p[9], b)):
                        i = pod.get(inst)
                        if i is None:
                            i = pod[inst] = len(member)
                            member.append(g)
                        ids.append(i)
                    if ids[0] == ids[1]:
                        self_calls += 1  # a pod calling itself never crosses the network
                    else:
                        q.append((ids[0], ids[1], r))
    rng = random.Random(0)
    npods = len(member)
    rnd = [(rng.randrange(npods), rng.randrange(npods), rng.randrange(len(RELS))) for _ in range(len(q))]
    w = lambda name, arr: np.asarray(arr, dtype="<u4").tofile(os.path.join(OUT, name))  # noqa: E731
    w("member.u32", member)
    w("rules.u32", sorted(rules))
    w("queries.u32", q)
    w("random.u32", rnd)
    # 50-microservice subset of E1 (same selection), with names mapped to this file's ids
    with open(os.path.join(ROOT, "derived", "alibaba_callgraph_w0.pkl"), "rb") as fh:
        w0 = pickle.load(fh)
    names = {w0["ms_names"][i] for i in subset(w0, 50)}
    sel = {ms[n] for n in names if n in ms}
    srules = [t for t in rules if t[0] in sel and t[2] in sel]
    pods_of = {}
    for i, g in enumerate(member):
        if g in sel:
            pods_of.setdefault(g, []).append(i)
    pairwise = [(x, y, r) for a, r, b in srules for x in pods_of.get(a, ()) for y in pods_of.get(b, ()) if x != y]
    sq = [t for t in q if member[t[0]] in sel and member[t[1]] in sel]
    w("subset_rules.u32", sorted(srules))
    w("subset_queries.u32", sq)
    w("pairwise.u32", pairwise)
    meta = {"pods": npods, "groups": len(ms), "rules": len(rules), "queries": len(q), "relations": len(RELS),
            "subset_microservices": len(sel), "subset_rules": len(srules), "subset_queries": len(sq),
            "subset_pods": sum(len(v) for v in pods_of.values()), "pairwise_rules": len(pairwise), "self_calls_dropped": self_calls}
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
    print(meta)


if __name__ == "__main__":
    main()
