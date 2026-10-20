# E1: IMS processing and compilation on the Alibaba v2022 east-west topology (window 0)

Times in ms, mean ± std over runs (10 for policy stages and group compilation, 3 for per-pair compilation). Laptop: Ryzen 5 7530U, 15.4 GB RAM, Python 3.12, one thread, GC off during timing.

| Microservices | Pods | Intents | Constraints | Compose | Verify (window-1 edges) | Drift | Group compile | Group rules | Group peak MB | Per-pair rules | Per-pair compile | Per-pair peak MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 50 | 6,332 | 131 | 19 | 0.2 ± 0.1 | 0.2 ± 0.0 | 1.7% | 0.2 ± 0.0 | 132 | 0.3 | 1,643,196 | 1718.9 ± 59.0 | 456 |
| 102 | 11,408 | 230 | 36 | 0.4 ± 0.0 | 0.4 ± 0.0 | 6.4% | 0.3 ± 0.1 | 232 | 0.6 | 9,611,755 | ~0.2 min (projected) | ~2,671 (projected) |
| 222 | 45,358 | 653 | 74 | 0.9 ± 0.1 | 0.9 ± 0.1 | 7.1% | 1.0 ± 0.1 | 660 | 2.6 | 490,485,087 | ~8.6 min (projected) | ~136,276 (projected) |
| 404 | 57,582 | 1,302 | 128 | 1.6 ± 0.1 | 2.1 ± 0.4 | 7.8% | 1.3 ± 0.1 | 1,310 | 2.7 | 590,236,962 | ~10.3 min (projected) | ~163,991 (projected) |
| 1,000 | 100,537 | 3,833 | 257 | 4.4 ± 0.4 | 6.1 ± 1.5 | 9.3% | 2.6 ± 0.1 | 3,850 | 5.5 | 828,356,806 | ~14.5 min (projected) | ~230,151 (projected) |
| 2,016 | 149,030 | 8,576 | 486 | 9.6 ± 0.5 | 10.8 ± 0.3 | 11.0% | 4.4 ± 0.6 | 8,614 | 6.1 | 1,146,147,147 | ~20.0 min (projected) | ~318,445 (projected) |
| 4,000 | 206,401 | 16,748 | 892 | 21.5 ± 4.6 | 21.6 ± 1.8 | 12.6% | 7.1 ± 0.3 | 16,812 | 12.2 | 1,380,400,412 | ~24.1 min (projected) | ~383,530 (projected) |
| 8,002 | 270,249 | 31,280 | 1,778 | 33.3 ± 2.3 | 40.6 ± 2.9 | 14.4% | 12.3 ± 0.4 | 31,403 | 14.0 | 1,629,006,251 | ~28.4 min (projected) | ~452,603 (projected) |
| 16,291 | 314,363 | 50,783 | 3,738 | 63.3 ± 4.4 | 69.3 ± 3.1 | 17.7% | 20.5 ± 1.3 | 50,935 | 17.0 | 1,676,043,911 | ~29.2 min (projected) | ~465,672 (projected) |

Per-pair compilation measured cost: 1.05 µs and 291 bytes per rule (largest measured size); projections use these.

Drift = share of window-1 (next 3 minutes) relation triples that the window-0 policy does not allow.
