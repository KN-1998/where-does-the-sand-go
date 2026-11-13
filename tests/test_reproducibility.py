"""T8 integration test for deterministic artifact outputs."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.exp.run_one import main


class ReproducibilityTests(unittest.TestCase):
    def test_same_seed_outputs_identical_results_and_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            args = ["--config", str(ROOT / "configs" / "no_storm.yaml"),
                    "--strategy", "none"]
            self.assertEqual(main([*args, "--out", str(first)]), 0)
            self.assertEqual(main([*args, "--out", str(second)]), 0)
            self.assertEqual((first / "results.json").read_bytes(),
                             (second / "results.json").read_bytes())
            digest = lambda path: hashlib.md5(path.read_bytes()).hexdigest()
            self.assertEqual(digest(first / "fields.npz"), digest(second / "fields.npz"))
            self.assertNotIn(b"run_seconds", (first / "results.json").read_bytes())

    def test_cli_overrides_are_in_resolved_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "override"
            self.assertEqual(main([
                "--config", str(ROOT / "configs" / "base.yaml"),
                "--scenario", "S2", "--seed", "7", "--bc", "open",
                "--t-end", "0.5", "--out", str(out),
            ]), 0)
            data = json.loads((out / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(data["parameters"]["scenario"], "S2")
            self.assertEqual(data["parameters"]["seed"], 7)
            self.assertEqual(data["parameters"]["bc"], "open")
            self.assertEqual(data["parameters"]["t_end"], 0.5)

    def test_paired_retention_uses_shared_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "paired"
            self.assertEqual(main([
                "--config", str(ROOT / "configs" / "base.yaml"),
                "--strategy", "uniform", "--paired-retention",
                "--out", str(out),
            ]), 0)
            data = json.loads((out / "results.json").read_text(encoding="utf-8"))
            self.assertIn("R_ret_1yr", data["retention"])
            self.assertGreaterEqual(data["retention"]["R_ret_1yr"], 0.0)


if __name__ == "__main__":
    unittest.main()
