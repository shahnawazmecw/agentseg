"""Extract the east-west topology of one Alibaba v2022 CallGraph window (3 minutes).

Keeps calls whose caller (um) and callee (dm) are both microservices (MS_*); USER (external
entry), UNKNOWN and UNAVAILABLE endpoints and malformed rows are counted and dropped.
Pods are kept only when the instance id is a real pod (contains _POD_).

Output (pickle): ms names, pods per microservice, edges (um, dm) -> {rpctype: calls},
services -> microservices, and row counts.

Usage: python e1/prep_alibaba.py WINDOW_INDEX [WINDOW_INDEX ...]
"""
import collections
import io
import os
import pickle
import sys
import tarfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "datasets"))
SRC = os.path.join(ROOT, "D2_alibaba_microservices_v2022", "CallGraph", "CallGraph_{}.tar.gz")
DST = os.path.join(ROOT, "derived", "alibaba_callgraph_w{}.pkl")


def prep(w):
    t0 = time.time()
    ms_id, pod_id = {}, {}
    pods = collections.defaultdict(set)
    edges = collections.defaultdict(collections.Counter)
    services = collections.defaultdict(set)
    pod_pairs = set()
    counts = collections.Counter()

    def ms(name):
        i = ms_id.get(name)
        if i is None:
            i = ms_id[name] = len(ms_id)
        return i

    def pod(m, inst):
        if "_POD_" not in inst:
            return None
        i = pod_id.get(inst)
        if i is None:
            i = pod_id[inst] = len(pod_id)
        pods[m].add(i)
        return i

    with tarfile.open(SRC.format(w), mode="r:gz") as tf:
        for member in tf:
            fh = io.TextIOWrapper(tf.extractfile(member), encoding="utf-8", errors="replace")
            next(fh)
            for line in fh:
                p = line.rstrip("\n").split(",")
                counts["rows"] += 1
                if len(p) != 11:
                    counts["malformed"] += 1
                    continue
                _, _, service, _, rpctype, um, umi, _, dm, dmi, _ = p
                if not (um.startswith("MS_") and dm.startswith("MS_")):
                    counts["non_ms_endpoint"] += 1
                    continue
                counts["kept"] += 1
                a, b = ms(um), ms(dm)
                edges[(a, b)][rpctype] += 1
                services[service].update((a, b))
                pa, pb = pod(a, umi), pod(b, dmi)
                if pa is not None and pb is not None:
                    pod_pairs.add((pa << 20) | pb)
    out = {
        "window": w, "ms_names": list(ms_id), "pods": {m: sorted(s) for m, s in pods.items()},
        "n_pods": len(pod_id), "edges": {k: dict(v) for k, v in edges.items()},
        "services": {s: sorted(v) for s, v in services.items()},
        "distinct_pod_pairs": len(pod_pairs), "counts": dict(counts),
    }
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST.format(w), "wb") as fh:
        pickle.dump(out, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"window {w}: {dict(counts)}; microservices {len(ms_id)}, pods {len(pod_id)}, "
          f"ms edges {len(edges)}, services {len(services)}, distinct pod pairs {len(pod_pairs)}, "
          f"{time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    for w in sys.argv[1:]:
        prep(int(w))
