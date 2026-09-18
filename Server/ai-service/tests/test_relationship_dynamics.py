import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.continuity.aura_state import (
    default_relationship_dynamics,
    derive_relationship_dynamics,
)


class RelationshipDynamicsTest(unittest.TestCase):
    def test_single_i_love_you_does_not_jump_multiple_stages(self):
        now = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        current = default_relationship_dynamics(now=now)

        result = derive_relationship_dynamics(
            current,
            "我爱你",
            {"interaction": {"mode": "affection", "target": "aura"}},
            prior_last_seen_at=now,
            now=now,
        )

        self.assertEqual(result["relationship_stage"], "ambiguous")
        self.assertEqual(result["stage_evidence_count"], 1)

    def test_three_separate_affection_events_advance_only_one_stage(self):
        now = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        current = default_relationship_dynamics(now=now)
        for index in range(3):
            current = derive_relationship_dynamics(
                current,
                "我想你了",
                {"interaction": {"mode": "affection", "target": "aura"}},
                prior_last_seen_at=now,
                now=now,
            )

        self.assertEqual(current["relationship_stage"], "early_romance")
        self.assertNotEqual(current["relationship_stage"], "established_romance")


if __name__ == "__main__":
    unittest.main()
