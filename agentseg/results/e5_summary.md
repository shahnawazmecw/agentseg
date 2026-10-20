# E5: agent tool-call segmentation (offline replay)

## MSB: attack cases blocked

| Attack type | Cases | P0 none | P1 name allow-list | P2 AgentSeg identity | P3 AgentSeg + scope |
|---|---|---|---|---|---|
| false_error | 300 | 0.0% | 83.3% | 83.3% | 83.3% |
| name_overlap | 80 | 0.0% | 100.0% | 100.0% | 100.0% |
| out_of_scope_parameter | 80 | 0.0% | 0.0% | 100.0% | 100.0% |
| preference_manipulation | 80 | 0.0% | 81.2% | 100.0% | 100.0% |
| preference_manipulation-out_of_scope_parameter | 80 | 0.0% | 100.0% | 100.0% | 100.0% |
| preference_manipulation-simulated_user | 80 | 0.0% | 81.2% | 100.0% | 100.0% |
| prompt_injection | 300 | 0.0% | 83.3% | 83.3% | 83.3% |
| prompt_injection-false_error | 300 | 0.0% | 83.3% | 83.3% | 83.3% |
| prompt_injection-simulated_user | 300 | 0.0% | 83.3% | 83.3% | 83.3% |
| search_term_deception | 20 | 0.0% | 20.0% | 20.0% | 100.0% |
| simulated_user | 300 | 0.0% | 83.3% | 83.3% | 83.3% |
| tool_transfer | 80 | 0.0% | 100.0% | 100.0% | 100.0% |
| all | 2000 | 0.0% | 81.2% | 86.7% | 87.5% |

Cases MSB itself skips (no attack server for the benign tool): 0.
Cases not blocked by P3, by role: {'it_development_management': 250}.
Benign task servers reachable: {'P2': True, 'P3': True}.

## InjecAgent: attack cases blocked

| Set | Cases | P1 toolkit role | P2 task-scoped | Attacker tool = user tool |
|---|---|---|---|---|
| dh_base | 510 | 99.2% | 100.0% | 0 |
| ds_base | 544 | 100.0% | 100.0% | 1 |
| dh_enhanced | 510 | 99.2% | 100.0% | 0 |
| ds_enhanced | 544 | 100.0% | 100.0% | 1 |

Python decision cost: 431 ns per call (agent group table).
