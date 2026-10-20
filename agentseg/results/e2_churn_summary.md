# E2b: churn replay on Alibaba v2022 (minutes 30–75)

Policy learned from minutes 0–30; 3 repeats of the replay; laptop, one thread, GC off during timing.

## Policy events, full scale (per 3-minute window)

| Window | New triples | Admitted | AgentSeg incremental (ms) | IMS recompose (ms) | Speed-up |
|---|---|---|---|---|---|
| 10 | 1,840 | 1,361 | 11.76 ± 2.85 | 167.13 ± 27.43 | 14x |
| 11 | 1,534 | 1,141 | 7.61 ± 0.81 | 152.72 ± 15.75 | 20x |
| 12 | 1,545 | 1,144 | 9.79 ± 2.60 | 169.42 ± 26.59 | 17x |
| 13 | 1,605 | 1,216 | 11.27 ± 2.25 | 155.50 ± 10.16 | 14x |
| 14 | 2,187 | 1,640 | 9.72 ± 0.17 | 162.88 ± 25.38 | 17x |
| 15 | 3,096 | 2,388 | 15.35 ± 4.17 | 195.70 ± 60.51 | 13x |
| 16 | 4,465 | 3,464 | 20.80 ± 6.20 | 177.38 ± 45.02 | 9x |
| 17 | 4,895 | 3,848 | 22.07 ± 3.03 | 210.27 ± 80.42 | 10x |
| 18 | 4,099 | 3,181 | 20.15 ± 3.88 | 233.62 ± 75.71 | 12x |
| 19 | 1,754 | 1,393 | 9.01 ± 2.22 | 246.73 ± 77.54 | 27x |
| 20 | 1,010 | 778 | 5.16 ± 1.66 | 202.48 ± 40.70 | 39x |
| 21 | 642 | 509 | 4.73 ± 2.14 | 174.03 ± 13.87 | 37x |
| 22 | 453 | 351 | 3.42 ± 0.67 | 214.89 ± 41.66 | 63x |
| 23 | 644 | 461 | 6.01 ± 3.73 | 213.45 ± 43.28 | 35x |
| 24 | 507 | 379 | 5.35 ± 2.78 | 184.09 ± 21.72 | 34x |

Pod events, full scale: 613 births and deaths over 45 minutes; AgentSeg membership updates 2.95 µs per event on average (batch time / events, repeat 0).

## Pod events, subset where IMS per-pair rules fit

203 microservices, 1,933 pods, 205,219 per-pair rules at minute 30; 57 pod events replayed.

| | Mean | p99 |
|---|---|---|
| IMS Algorithm 6 (ms) | 0.23 ± 0.05 | 1.61 ± 1.47 |
| AgentSeg membership (µs) | 0.99 ± 0.20 | 5.60 ± 4.45 |

IMS rewrites 241 flow rules per event on average.
