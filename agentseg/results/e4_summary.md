# E4: lateral-movement containment (LANL, 58 days)

455,931,462 network authentications among 17,647 computers; 749 red-team authentications from 4 source computers, the first at 150,885 s (41.9 h).

## Red-team authentications denied / legitimate later authentications denied

| Learned over | user_pair | pair | user_dst | dst |
|---|---|---|---|---|
| first 6 h | 100.0% / 70.23% | 100.0% / 66.94% | 95.3% / 65.36% | 18.4% / 1.73% |
| first 12 h | 100.0% / 42.93% | 100.0% / 37.66% | 85.2% / 38.30% | 10.5% / 0.58% |
| first 24 h | 100.0% / 37.25% | 100.0% / 32.43% | 83.6% / 32.83% | 10.3% / 0.50% |
| first 41 h | 100.0% / 29.82% | 100.0% / 25.42% | 77.3% / 25.65% | 8.5% / 0.37% |

Legitimate denials are counted over all of the remaining days (a long horizon).

## Legitimate authentications denied in the 24 h after learning

| Learned over | Events | user_pair | pair | user_dst | dst |
|---|---|---|---|---|---|
| first 6 h | 7,922,481 | 57.64% | 54.37% | 53.44% | 1.29% |
| first 12 h | 7,944,088 | 16.49% | 13.05% | 14.60% | 0.13% |
| first 24 h | 8,160,574 | 13.77% | 10.70% | 12.08% | 0.15% |
| first 41 h | 7,322,420 | 7.66% | 5.40% | 6.42% | 0.05% |

## Blast radius of the red-team source computers (pair policy)

| Learned over | Source | Direct | Transitive | Red-team targets | Targets directly allowed |
|---|---|---|---|---|---|
| 6 h | C17693 | 0 | 0 | 296 | 0 |
| 6 h | C18025 | 0 | 0 | 1 | 0 |
| 6 h | C19932 | 0 | 0 | 8 | 0 |
| 6 h | C22409 | 0 | 0 | 3 | 0 |
| 12 h | C17693 | 0 | 0 | 296 | 0 |
| 12 h | C18025 | 0 | 0 | 1 | 0 |
| 12 h | C19932 | 0 | 0 | 8 | 0 |
| 12 h | C22409 | 0 | 0 | 3 | 0 |
| 24 h | C17693 | 0 | 0 | 296 | 0 |
| 24 h | C18025 | 0 | 0 | 1 | 0 |
| 24 h | C19932 | 0 | 0 | 8 | 0 |
| 24 h | C22409 | 0 | 0 | 3 | 0 |
| 41 h | C17693 | 5 | 1,540 | 296 | 0 |
| 41 h | C18025 | 0 | 0 | 1 | 0 |
| 41 h | C19932 | 0 | 0 | 8 | 0 |
| 41 h | C22409 | 0 | 0 | 3 | 0 |

Without segmentation every computer is reachable: 17,647.
