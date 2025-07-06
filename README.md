[comment]: # "v0"
# MLaaS GPU Cluster Performance Modeling and Simulation

## Overview

This project analyzes and models the performance of a large-scale heterogeneous GPU cluster running Machine Learning as a Service (MLaaS), inspired by Alibaba’s production system as described in the paper ["MLaaS in the Wild: Workload Analysis and Scheduling in Large-Scale Heterogeneous GPU Clusters"](https://arxiv.org/abs/2007.01235).

The goal is to use real workload traces ([Alibaba Cluster Trace v2020, GPU edition](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2020)), queueing theory, and discrete-event simulation to:
- Understand system bottlenecks
- Analyze scheduling and resource allocation policies
- Propose and evaluate improvements

---

## System Description

The studied system consists of a large GPU cluster hosting a mix of ML workloads:
- **Diverse job classes:** Short/long, low/high GPU demand, different ML frameworks (e.g., TensorFlow, PyTorch)
- **Dynamic resource management:** GPU sharing (time-multiplexing), packing strategies, and autoscaling
- **Key challenges:** Underutilization, queueing delays (esp. for short jobs), head-of-line blocking, CPU-GPU imbalance

---

## Project Objectives

- **Model Construction:** Build an analytical (queueing theory) and simulation model of the MLaaS cluster.
- **Validation:** Use real cluster trace data to validate model accuracy.
- **Bottleneck Analysis:** Identify sources of delay and resource contention.
- **Optimization:** Evaluate improvements such as predictive scheduling and enhanced GPU sharing.

---

## Data

Workload trace data is sourced from the Alibaba Cluster Trace Program:

- [Alibaba Cluster GPU Trace (2020)](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2020)
- Trace includes: Job arrival times, durations, GPU/CPU requirements, placement, and more

---

## Repository Structure

```
.
├── README.md               # Project overview and instructions
├── data/                   # Scripts to preprocess and analyze the Alibaba trace
├── analysis/               # Analytical queueing model scripts/notebooks
├── simulation/             # Discrete-event simulation code and configs
├── results/                # Generated plots, tables, and summaries
├── report/                 # Project report, write-up, and references
└── utils/                  # Shared utilities (plotting, data loading, etc.)
```

---

## Getting Started

1. **Clone the repository**
   ```bash
   git clone <repo_url>
   cd <repo_name>
   ```

2. **Download the Alibaba trace data**
   - Place data files in the `data/` directory.

3. **Environment Setup**
   - Install Python 3.x and required libraries:
     ```bash
     pip install -r requirements.txt
     ```

4. **Run Analyses and Simulations**
   - Analytical modeling scripts: `analysis/`
   - Simulation experiments: `simulation/`
   - Results and plots: `results/`

5. **View Report**
   - See the `report/` directory for detailed write-up and final results.

---

## References

- Wang, Y., et al., "MLaaS in the Wild: Workload Analysis and Scheduling in Large-Scale Heterogeneous GPU Clusters", [arXiv:2007.01235](https://arxiv.org/abs/2007.01235)
- [Alibaba Cluster Trace Program](https://github.com/alibaba/clusterdata)


