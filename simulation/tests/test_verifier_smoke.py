import csv
import os
import subprocess
import sys
import tempfile
import unittest


def _write_summary(path: str) -> None:
    rows = [
        ("tickets_arrived", 2),
        ("tickets_closed", 2),
        ("closure_rate", 1.0),
        ("mean_time_in_system", 4.1),
        ("avg_wait_dev", 0.75),
        ("avg_wait_review", 0.35),
        ("avg_wait_testing", 0.15),
        ("avg_queue_length_dev", 0.1),
        ("avg_queue_length_review", 0.1),
        ("avg_queue_length_testing", 0.1),
        ("avg_servers_dev", 1.0),
        ("avg_servers_review", 1.0),
        ("avg_servers_testing", 1.0),
        ("utilization_dev", 0.5),
        ("utilization_review", 0.5),
        ("utilization_testing", 0.5),
        ("avg_system_length_dev", 0.6),
        ("avg_system_length_review", 0.6),
        ("avg_system_length_testing", 0.6),
    ]

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


def _write_tickets(path: str) -> None:
    rows = [
        {
            "ticket_id": "1",
            "closed_time": "1.0",
            "wait_dev": "1.0",
            "wait_review": "0.5",
            "wait_testing": "0.2",
            "service_time_dev": "2.0",
            "service_time_review": "1.0",
            "service_time_testing": "0.5",
            "total_wait": "1.7",
            "time_in_system": "5.2",
            "dev_cycles": "1",
            "review_cycles": "1",
            "test_cycles": "1",
        },
        {
            "ticket_id": "2",
            "closed_time": "1.0",
            "wait_dev": "0.5",
            "wait_review": "0.2",
            "wait_testing": "0.1",
            "service_time_dev": "1.0",
            "service_time_review": "0.8",
            "service_time_testing": "0.4",
            "total_wait": "0.8",
            "time_in_system": "3.0",
            "dev_cycles": "1",
            "review_cycles": "1",
            "test_cycles": "1",
        },
    ]

    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class VerificationSmokeTest(unittest.TestCase):
    """Run the verifier against a synthetic, self-consistent dataset."""

    def test_verify_succeeds_on_synthetic_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = os.path.join(tmpdir, "summary_stats.csv")
            tickets_path = os.path.join(tmpdir, "tickets_stats.csv")
            _write_summary(summary_path)
            _write_tickets(tickets_path)

            result = subprocess.run(
                [sys.executable, "-m", "simulation.verify", "--input", tmpdir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self.fail(
                    f"Verifier exited with {result.returncode}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                )

            report_path = os.path.join(tmpdir, "verification_report.md")
            self.assertTrue(os.path.exists(report_path), "Verification report was not created")


if __name__ == "__main__":
    unittest.main()
