"""Pod lifetimes from the Alibaba v2022 MSMetrics table (one sample per running pod per minute).

Output (pickle, ../datasets/derived/alibaba_pod_lifecycle.pkl):
  pods: {pod name: [microservice name, first ms timestamp, last ms timestamp]}
  span: [first, last] timestamp over all samples; files: the MSMetrics files read.

Usage: python e2/prep_lifecycle.py   (reads MSMetrics_0..3, the first 2 hours)
"""
import io
import os
import pickle
import tarfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "datasets"))
SRC = os.path.join(ROOT, "D2_alibaba_microservices_v2022", "MSMetrics", "MSMetrics_{}.tar.gz")
DST = os.path.join(ROOT, "derived", "alibaba_pod_lifecycle.pkl")


def main(files=(0, 1, 2, 3)):
    pods, lo, hi, rows, bad = {}, None, None, 0, 0
    for i in files:
        t0 = time.time()
        with tarfile.open(SRC.format(i), mode="r:gz") as tf:
            for member in tf:
                fh = io.TextIOWrapper(tf.extractfile(member), encoding="utf-8", errors="replace")
                next(fh)
                for line in fh:
                    p = line.split(",", 4)
                    rows += 1
                    if len(p) < 4 or "_POD_" not in p[2]:
                        bad += 1
                        continue
                    ts = int(p[0])
                    rec = pods.get(p[2])
                    if rec is None:
                        pods[p[2]] = [p[1], ts, ts]
                    else:
                        if ts < rec[1]:
                            rec[1] = ts
                        if ts > rec[2]:
                            rec[2] = ts
                    lo = ts if lo is None or ts < lo else lo
                    hi = ts if hi is None or ts > hi else hi
        print(f"MSMetrics_{i}: {len(pods):,} pods so far, {time.time() - t0:.0f} s", flush=True)
    with open(DST, "wb") as fh:
        pickle.dump({"pods": pods, "span": [lo, hi], "files": list(files), "rows": rows, "skipped_rows": bad},
                    fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"{rows:,} rows, {bad:,} skipped, {len(pods):,} pods, span {lo}..{hi} ms", flush=True)


if __name__ == "__main__":
    main()
