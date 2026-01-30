# Validation report templates

This directory stores Markdown snippets used by `simulation.validate` when rendering per-scenario reports. Templates are kept lightweight so they can be embedded directly in generated outputs.

## Verification vs. validation tooling

- `simulation/verify.py` performs **internal consistency checks only** (e.g., schema alignment, deterministic expectations, and invariants). It does **not** compare simulation output to external baselines.
- `simulation/validate.py` performs **simulation vs. ETL baseline comparisons** and renders reports using the templates in this directory.

### When to use which

- Use **`simulation/verify.py`** when you need to confirm the simulation artifacts are self-consistent or to debug perfectly equal checks that are expected to match exactly.
- Use **`simulation/validate.py`** when you need to confirm the simulation aligns with ETL-derived baselines and want to interpret any differences in reported metrics.
