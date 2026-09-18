import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.continuity.aura_state import (
    default_relationship_dynamics,
    derive_affect_states,
    derive_relationship_dynamics,
    derive_relationship_events,
    summarize_affects,
)


class RelationshipDynamicsTest(unittest.TestCase):
    def test_affection_does_not_promote_stage_by_count(self):
        now = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        current = default_relationship_dynamics(now=now)
        for index in range(5):
            observed_at = now + timedelta(minutes=index)
            current = derive_relationship_dynamics(
                current,
                "我爱你",
                {"interaction": {"mode": "affection", "target": "aura"}},
                prior_last_seen_at=now,
                now=observed_at,
            )

        self.assertEqual(current["relationship_stage"], "ambiguous")
        self.assertEqual(current["relationship_phase"], "normal")
        self.assertEqual(current["relationship_tone"], "tender")
        self.assertNotIn("stage_evidence_count", current)

    def test_distance_changes_phase_without_erasing_romance_stage(self):
        now = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        current = {
            **default_relationship_dynamics(now=now),
            "relationship_stage": "established_romance",
        }

        result = derive_relationship_dynamics(
            current,
            "我回来了",
            {"interaction": {"mode": "natural", "target": "aura"}},
            prior_last_seen_at=now - timedelta(days=4),
            now=now,
        )

        self.assertEqual(result["relationship_stage"], "established_romance")
        self.assertEqual(result["relationship_phase"], "distant")
        self.assertEqual(result["relationship_tone"], "guarded")

    def test_conflict_repair_and_completion_only_change_phase(self):
        now = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        current = {
            **default_relationship_dynamics(now=now),
            "relationship_stage": "early_romance",
        }
        conflict = derive_relationship_dynamics(
            current,
            "你根本不在乎我",
            {},
            prior_last_seen_at=now,
            now=now,
        )
        repairing = derive_relationship_dynamics(
            conflict,
            "对不起，我错了",
            {},
            prior_last_seen_at=now,
            now=now + timedelta(minutes=5),
        )
        repaired = derive_relationship_dynamics(
            repairing,
            "我最喜欢你，别生气",
            {"interaction": {"mode": "affection", "target": "aura"}},
            prior_last_seen_at=now,
            now=now + timedelta(minutes=10),
        )

        self.assertEqual(conflict["relationship_phase"], "conflict")
        self.assertEqual(repairing["relationship_phase"], "repair")
        self.assertEqual(repaired["relationship_phase"], "normal")
        self.assertEqual(repaired["relationship_stage"], "early_romance")

    def test_explicit_milestone_can_advance_one_stage(self):
        now = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        result = derive_relationship_dynamics(
            default_relationship_dynamics(now=now),
            "我们在一起吧",
            {"interaction": {"mode": "affection", "target": "aura"}},
            prior_last_seen_at=now,
            now=now,
        )

        self.assertEqual(result["relationship_stage"], "early_romance")


class RelationshipEventTest(unittest.TestCase):
    def test_turn_produces_auditable_event_types(self):
        now = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        events = derive_relationship_events(
            "今天跟一个女生吃饭了",
            {},
            relationship_phase="normal",
            prior_last_seen_at=now - timedelta(hours=13),
            now=now,
        )

        self.assertEqual(
            {item["type"] for item in events},
            {"important_disclosure", "return_after_absence"},
        )


class AffectStateTest(unittest.TestCase):
    def test_jealousy_persists_then_fades_and_expires(self):
        started = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        event = {"type": "important_disclosure", "payload": {"affect": "jealousy"}}
        initial = derive_affect_states([], "跟女生吃饭", [event], now=started)
        after_twelve_hours = derive_affect_states(
            initial,
            "早",
            [],
            now=started + timedelta(hours=12),
        )
        expired = derive_affect_states(
            after_twelve_hours,
            "晚安",
            [],
            now=started + timedelta(hours=25),
        )

        self.assertEqual(summarize_affects(initial, now=started)["jealousy"], "low")
        self.assertEqual(after_twelve_hours[0]["decay_phase"], "fading")
        self.assertEqual(
            summarize_affects(expired, now=started + timedelta(hours=25))["jealousy"],
            "none",
        )

    def test_related_event_reinforces_and_reassurance_resolves(self):
        started = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        event = {"type": "important_disclosure", "payload": {"affect": "jealousy"}}
        initial = derive_affect_states([], "第一次", [event], now=started)
        reinforced = derive_affect_states(
            initial,
            "又和她见面了",
            [event],
            now=started + timedelta(hours=2),
        )
        resolved = derive_affect_states(
            reinforced,
            "我只喜欢你，别吃醋",
            [],
            now=started + timedelta(hours=3),
        )

        self.assertEqual(reinforced[0]["intensity"], "medium")
        self.assertTrue(resolved[0]["resolved"])

    def test_each_affect_keeps_its_own_source_event(self):
        now = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        events = [
            {"type": "important_disclosure", "payload": {"affect": "jealousy"}},
            {"type": "return_after_absence", "payload": {}},
        ]

        affects = derive_affect_states(
            [],
            "我回来了，刚才跟一个女生吃饭",
            events,
            now=now,
            source_event_ids={
                "important_disclosure": "jealousy-event",
                "return_after_absence": "return-event",
            },
        )

        by_kind = {item["kind"]: item for item in affects}
        self.assertEqual(by_kind["jealousy"]["source_event_id"], "jealousy-event")
        self.assertEqual(by_kind["longing"]["source_event_id"], "return-event")


if __name__ == "__main__":
    unittest.main()
