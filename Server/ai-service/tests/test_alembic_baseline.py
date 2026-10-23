from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AlembicBaselineTests(unittest.TestCase):
    def test_baseline_and_environment_are_checked_in(self) -> None:
        config = (ROOT / "alembic.ini").read_text(encoding="utf-8")
        environment = (ROOT / "alembic" / "env.py").read_text(encoding="utf-8")
        baseline = (
            ROOT / "alembic" / "versions" / "20260918_0001_current_schema.py"
        ).read_text(encoding="utf-8")

        self.assertIn("script_location", config)
        self.assertIn("Base.metadata", environment)
        self.assertIn('revision: str = "20260918_0001"', baseline)
        self.assertIn("stamp", baseline)


if __name__ == "__main__":
    unittest.main()
