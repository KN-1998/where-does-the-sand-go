"""Configuration inheritance regression tests."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim.io import load_config


class ConfigTests(unittest.TestCase):
    def test_recursive_no_storm_inheritance(self):
        config = load_config(ROOT / "configs" / "no_storm.yaml")
        self.assertFalse(config["storm_enabled"])
        self.assertEqual(config["scenario"], "S1")
        self.assertEqual(config["domain"]["L_corridor"]["value"], 5000.0)
        self.assertEqual(config["numerics"]["dx"]["value"], 25.0)

    def test_inheritance_cycle_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.yaml").write_text("inherit: b.yaml\n", encoding="utf-8")
            (root / "b.yaml").write_text("inherit: a.yaml\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inheritance cycle"):
                load_config(root / "a.yaml")


if __name__ == "__main__":
    unittest.main()
