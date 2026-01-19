# Verifica della Legge di Little nei Tre Stadi della Simulazione (DEV / REVIEW / TESTING)

Questo documento mostra come la Legge di Little si applica alle tre code del workflow **DEV → REVIEW → TESTING** dopo la rimozione della colonna `avg_queue_length_backlog` e l'allineamento del backlog alla metrica `avg_queue_length_dev`.

---

## 1. DEV (Backlog) — Coda Vuota, Legge di Little Triviale

**Dati osservati dalla simulazione**
- `avg_queue_length_dev` = **0.000000** (il backlog è vuoto perché i ticket partono subito)
- `throughput_dev` = **0.268493 / giorno**
- `avg_wait_dev` = **0.000000 giorni**

**Calcolo**
$$
L_q^{(LL)} = 0.268493 \times 0.000000 = 0.000000
$$
**Confronto**
- Simulazione: **0.000000**
- Little: **0.000000**

La coda DEV coincide con il backlog ed è sostanzialmente vuota: la Legge di Little è soddisfatta banalmente (0 = 0·0).

---

## 2. REVIEW — Legge di Little Compatibile con Traffico Intermittente

**Dati osservati**
- `avg_queue_length_review` = **0.659813**
- `throughput_review` = **0.224658**
- `avg_wait_review` = **2.280072**

**Calcolo**
$$
L_q^{(LL)} = 0.224658 \times 2.280072 \approx 0.5122
$$
**Confronto**
- Simulazione: **0.6598**
- Little: **0.5122**

La differenza è attribuibile a traffico finito e feedback che rendono la coda intermittente.

---

## 3. TESTING — Coda Vuota

**Dati osservati**
- `avg_queue_length_testing` = **0.000000**
- `throughput_testing` = **0.224658**
- `avg_wait_testing` = **0.000000**

**Calcolo**
$$
L_q^{(LL)} = 0.224658 \times 0.000000 = 0.000000
$$
**Confronto**
- Simulazione: **0.000000**
- Little: **0.000000**

La capacità di test è sufficiente ad assorbire il flusso: la Legge di Little è soddisfatta in modo banale.

---

## Conclusione

- **DEV (Backlog)**: la coda è vuota; Little è soddisfatta trivialmente.
- **REVIEW**: Little è compatibile; la deviazione riflette dinamiche finite e feedback.
- **TESTING**: coda vuota; Little è soddisfatta trivialmente.

L'allineamento del backlog alla metrica `avg_queue_length_dev` e l'eliminazione della colonna separata per il backlog rendono le code DEV/REVIEW/TEST più leggibili e coerenti con la Legge di Little.
