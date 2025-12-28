# Sweep 5_2B Investigation — higher_arrival feedback drift

## Observed Differences
| Field | baseline | higher_arrival | feedback_heavy |
| --- | --- | --- | --- |
| arrival_rate | 0.3074951954 | 0.45 | 0.3074951954 |
| feedback_dev | 0.0 | 0.02 → **0.0 (fixed)** | 0.1 |
| feedback_test | 0.0 | 0.01 → **0.0 (fixed)** | 0.08 |
| churn_weight_add | 1.0 | 1.0 | 1.2 |
| markov_stint_scaler | 1.0 | 1.0 | 1.0 |
| global_seed | 22015001 | 22015011 | 22015021 |

## Root Cause
- The sweep spec `simulation/sweeps/5_2B_sweeps.csv` was manually authored and the `higher_arrival` row mistakenly included non-baseline feedback probabilities (0.02/0.01) even though its intent was to only raise arrival_rate. No generator script exists for this file, so the incorrect values originated directly from the CSV. 【F:simulation/sweeps/5_2B_sweeps.csv†L1-L6】
- The runner maps CSV columns directly to config overrides without altering semantics, so the drift was not introduced during loading/merge. 【F:simulation/run_sweeps.py†L30-L136】

## Is it a bug or intended?
- Documentation describes arrival and feedback parameters as independent axes and references the CSV as an example with baseline arrival/feedback pairs, implying `higher_arrival` should only adjust arrivals. 【F:docs/parameter_sweeps_5_2B.md†L14-L23】
- There is no alternate spec or naming hint that `higher_arrival` should change feedback. Conclusion: the feedback change was accidental—a bug in the sweep definition, not an intentional variant.

## Proposed Fix Options
1. **Enforce semantics (implemented):** Keep `higher_arrival` identical to `baseline` for feedback parameters and change only `arrival_rate`. Updated the CSV accordingly to 0.0/0.0. 【F:simulation/sweeps/5_2B_sweeps.csv†L3-L6】
2. **Reinterpret experiment meaning:** If feedback increases were desired, rename `higher_arrival` to reflect dual changes or document a combined arrival+feedback variant. This option would also require updating docs to clarify intent; not applied.

## Unified Diff (applied)
```
- higher_arrival,0.45,0.02,0.01,22015011,365.0,1.0,1.0
+ higher_arrival,0.45,0.0,0.0,22015011,365.0,1.0,1.0
```
