# // v1.2B-ASF-BK-Overview
### PMCSN ASF — ASF / BK Context Overview  
*(Synchronised with semi‑Markov policy and queueing interpretation; compliant with `GPT_INSTRUCTIONS.md`)*

---

## 1 ▪ Role of ASF in BK

**ASF** provides the methodological spine for the BK case study used in PMCSN.  
It unifies data extraction, analytics, and simulation to evaluate development workflows under **developer autonomy**.

---

## 2 ▪ Modeling Premises (Aligned)

- **States**: OFF, DEV, REV, TEST.  
- **Transitions**: Markov matrix \( P \) from observed sequences at ticket completions.  
- **Stints**: Empirical PMFs \( f_i(\ell) \) for consecutive task counts per state.  
- **Service‑times**: Log‑normal distributions \( T_s \) per stage.  
- **Queues**: DEV/REV/TEST as service centers with **dynamic server pools**.  
- **Feedback**: TEST → DEV rework path modeled explicitly.

---

## 3 ▪ Intended Use

1. **Analysis** — derive \( P, f_i, T_s \) (3.2A) and summarize assumptions.  
2. **Simulation** — run DES scenarios (4.x) using these parameters.  
3. **Validation** — compare occupancy and throughput vs traces (5–6).  
4. **Reporting** — compile findings for meetings 7–8.

---

## 4 ▪ Cross‑References

- `docs/CONCEPTUAL_WORKFLOW_MODEL_v1.2.md` — formal structure.  
- `docs/DERIVATIONS_3.2A.md` — equations & parameter derivations.  
- `Intro_Overview_Refresh_v1.3.md` — project‑level intro & objectives.

---

## 5 ▪ DoD

- Version banner present (v1.2B).  
- Terminology matches semi‑Markov & queueing conventions.  
- Links resolve inside repo; Markdown lint OK.

---

**End — ASF / BK Overview (v1.2B)**
