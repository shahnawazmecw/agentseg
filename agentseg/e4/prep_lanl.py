"""Aggregate the LANL authentication log for E4 (column-wise with pyarrow; 1.05 B events).

Keeps network authentications only (source computer != destination computer, neither '?').
For three policy keys it records, per distinct key, the first time it occurs and its event count:
  pair      (src_computer, dst_computer)
  user_dst  (src_user, dst_computer)
  user_pair (src_user, src_computer, dst_computer)
plus an hourly histogram of network authentications. One output per input file, so the script
resumes where it stopped. Output: ../datasets/derived/lanl_agg/
Usage: python e4/prep_lanl.py [--deadline SECONDS]
"""
import argparse
import glob
import os
import time

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "datasets"))
SRC = os.path.join(ROOT, "D3_lanl_sample", "auth")
DST = os.path.join(ROOT, "derived", "lanl_agg")
KEYS = {"pair": ["src_computer", "dst_computer"], "user_dst": ["src_user", "dst_computer"],
        "user_pair": ["src_user", "src_computer", "dst_computer"]}
HOURS = 58 * 24 + 1
CHUNK = 20  # row groups per batch (2 M rows)


def merge(tables, keys):
    t = pa.concat_tables(tables)
    g = t.group_by(keys).aggregate([("first", "min"), ("count", "sum")])
    return g.rename_columns(keys + ["first", "count"])


def one_file(path, stop_at):
    name = os.path.basename(path).split(".")[0]
    done = os.path.join(DST, f"{name}.done")
    if os.path.exists(done):
        return True
    f = pq.ParquetFile(path)
    parts = {k: [] for k in KEYS}
    hist = np.zeros(HOURS, dtype=np.int64)
    t0 = time.time()
    for start in range(0, f.metadata.num_row_groups, CHUNK):
        if time.time() > stop_at:
            return False  # nothing written for this file; it restarts next run
        t = f.read_row_groups(list(range(start, min(start + CHUNK, f.metadata.num_row_groups))),
                              columns=["time", "src_user", "src_computer", "dst_computer"])
        m = pc.and_(pc.not_equal(t["src_computer"], t["dst_computer"]),
                    pc.and_(pc.not_equal(t["src_computer"], "?"), pc.not_equal(t["dst_computer"], "?")))
        t = t.filter(m)
        tm = pc.cast(t["time"], pa.int64())
        t = t.set_column(0, "time", tm)
        hist += np.bincount(np.asarray(tm) // 3600, minlength=HOURS)[:HOURS]
        for k, cols in KEYS.items():
            g = t.group_by(cols).aggregate([("time", "min"), ("time", "count")])
            parts[k].append(g.rename_columns(cols + ["first", "count"]))
            if len(parts[k]) >= 25:
                parts[k] = [merge(parts[k], cols)]
    for k, cols in KEYS.items():
        pq.write_table(merge(parts[k], cols), os.path.join(DST, f"{name}_{k}.parquet"))
    np.save(os.path.join(DST, f"{name}_hours.npy"), hist)
    open(done, "w").close()
    print(f"{name}: {f.metadata.num_rows:,} rows in {time.time() - t0:.0f} s", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", type=float, default=500)
    args = ap.parse_args()
    stop_at = time.time() + args.deadline
    os.makedirs(DST, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(SRC, "*.parquet"))):
        if not one_file(path, stop_at):
            print("deadline reached; rerun to resume", flush=True)
            return
    print("all files done", flush=True)


if __name__ == "__main__":
    main()
