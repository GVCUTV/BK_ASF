# Verification Report
*Generated: 2025-12-28T18:34:09.755539Z*

- Input directory: `/home/cantarell/PycharmProjects/BK_ASF/simulation/output`
- Mode: single
- Tolerance: 1e-06
- Mean-jobs relative tolerance: 0.02

## Overall Status: ✅ PASS

### Run: /home/cantarell/PycharmProjects/BK_ASF/simulation/output
| Status | Check | Details |
| --- | --- | --- |
| ✅ | summary_stats.csv present | Found summary_stats.csv. |
| ✅ | tickets_stats.csv present | Found tickets_stats.csv. |
| ✅ | summary_stats.csv parsed | Loaded 30 metrics. |
| ✅ | tickets_stats.csv parsed | Loaded 110 rows. |
| ✅ | Stage entry inclusion rule | Per-stage means use only tickets with service_time>0 or cycles>0, matching queue_wait_records aggregation. |
| ✅ | Required summary metrics present | Found all required metrics: closure_rate, tickets_arrived, tickets_closed |
| ✅ | Summary metric bounds | Throughput, waits, queue lengths non-negative; utilizations within [0, 1]. |
| ✅ | Mean jobs identity (Little) | dev: avg_system_length_dev=6.020834, expected 6.020834 from queue 0.000000 + Ls 6.020834 (avg_servers=25.259467, utilization=0.238359) within ±2.00%; review: avg_system_length_review=7.545778, expected 7.545778 from queue 0.659813 + Ls 6.885965 (avg_servers=11.817707, utilization=0.582682) within ±2.00%; testing: avg_system_length_testing=0.059295, expected 0.059295 from queue 0.000000 + Ls 0.059295 (avg_servers=1.601713, utilization=0.037020) within ±2.00% |
| ✅ | Tickets arrived count | summary_stats.csv reports 110.0, tickets_stats.csv contains 110 rows. |
| ✅ | Tickets closed count | summary_stats.csv reports 82.0, detected 82 closed tickets. |
| ✅ | Closure rate | Reported 0.745455 vs computed 0.745455. |
| ✅ | Mean time in system | Reported 30.616363 vs computed 30.616363 from closed tickets. |
| ✅ | Ticket domain bounds | All waits and service times non-negative; time_in_system ≥ total_wait. |
| ✅ | Stage cycle consistency | Zero-cycle stages have zero wait and service time. |
| ✅ | Total wait decomposition | total_wait aligns with component waits. |
| ✅ | dev average wait | Summary avg_wait_dev=0.000000 vs micro mean 0.000000 (110 samples). Averages computed only over tickets that entered the stage (service_time>0 or cycles>0). |
| ✅ | review average wait | Summary avg_wait_review=2.280072 vs micro mean 2.280072 (94 samples). Averages computed only over tickets that entered the stage (service_time>0 or cycles>0). |
| ✅ | testing average wait | Summary avg_wait_testing=0.000000 vs micro mean 0.000000 (82 samples). Averages computed only over tickets that entered the stage (service_time>0 or cycles>0). |
| ✅ | dev Little identity | E[T]=336.638424 vs E[wait]+E[service]=336.638424 for 110 tickets. Inclusion rule: service_time>0 or cycles>0. |
| ✅ | review Little identity | E[T]=69.213941 vs E[wait]+E[service]=69.213941 for 94 tickets. Inclusion rule: service_time>0 or cycles>0. |
| ✅ | testing Little identity | E[T]=0.263936 vs E[wait]+E[service]=0.263936 for 82 tickets. Inclusion rule: service_time>0 or cycles>0. |
