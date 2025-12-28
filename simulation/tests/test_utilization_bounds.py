import os
import tempfile
import unittest

from simulation import run_sweeps


class UtilizationBoundsTest(unittest.TestCase):
    """Ensure stage utilizations remain within [0, 1] for key sweeps."""

    def test_utilization_within_bounds_for_core_sweeps(self) -> None:
        spec_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "sweeps", "5_2B_sweeps.csv")
        )
        experiments, param_columns = run_sweeps.load_sweep_spec(spec_path)
        target_ids = {"baseline", "higher_arrival", "feedback_heavy"}
        experiments = [exp for exp in experiments if exp.experiment_id in target_ids]
        self.assertTrue(experiments, "No experiments loaded for utilization bounds test")

        with tempfile.TemporaryDirectory() as tmpdir:
            for exp in experiments:
                success = run_sweeps.run_single_experiment(exp, tmpdir)
                self.assertTrue(success, f"Experiment {exp.experiment_id} failed")

            for exp in experiments:
                summary_path = os.path.join(tmpdir, exp.experiment_id, run_sweeps.SUMMARY_FILENAME)
                metrics = run_sweeps.read_summary_metrics(summary_path)
                for stage in ["dev", "review", "testing"]:
                    util = float(metrics.get(f"utilization_{stage}", 0.0))
                    self.assertGreaterEqual(util, 0.0, f"Utilization below 0 for {stage} in {exp.experiment_id}")
                    self.assertLessEqual(
                        util,
                        1.0,
                        f"Utilization above 1 for {stage} in {exp.experiment_id}: {util}",
                    )


if __name__ == "__main__":
    unittest.main()
