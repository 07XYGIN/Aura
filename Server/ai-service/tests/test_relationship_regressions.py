"""Cross-turn regressions for state changes, context and expression eligibility."""
import unittest
from datetime import UTC, datetime, timedelta

from langchain_core.messages import AIMessage, HumanMessage
from app.core.continuity.aura_state import (
    default_relationship_dynamics, derive_relationship_events,
    derive_relationship_dynamics, derive_affect_states, summarize_affects,
)
from app.core.agent.judges.impulse import judge_aura_impulse, recently_expressed
from app.core.agent.judges.emotion import infer_interaction_mode
from app.core.proactive.planner import relationship_contact_eligibility


class RelationshipEvidenceTest(unittest.TestCase):
    def test_non_assertions_do_not_create_events_even_with_affection_judgement(self):
        for text in (
            "我不喜欢你", "我没有跟女生约会", "小说里他说：我们在一起吧",
            "假如我说我们在一起吧，你会怎么回答", "你是我女朋友吗？",
            "翻译：我喜欢你", "她对我说我爱你", "以前我喜欢你",
            "不是说我喜欢你", "我喜欢你才怪", "如果跟女生吃饭，你会吃醋吗",
        ):
            with self.subTest(text=text):
                self.assertEqual(derive_relationship_events(text,
                    {"interaction": {"mode": "affection", "target": "aura"}},
                    relationship_phase="normal", prior_last_seen_at=None, now=datetime.now(UTC)), [])

    def test_clause_scope_preserves_affection_after_unrelated_negation(self):
        events = derive_relationship_events("我没出门，但我想你了", {}, relationship_phase="normal",
                                            prior_last_seen_at=None, now=datetime.now(UTC))
        self.assertEqual([e["type"] for e in events], ["affection_expressed"])

    def test_low_confidence_milestone_does_not_promote(self):
        events = derive_relationship_events("我们在一起吧",
            {"interaction": {"target": "aura", "confidence": 0.3}},
            relationship_phase="normal", prior_last_seen_at=None, now=datetime.now(UTC))
        self.assertNotIn("relationship_milestone", {e["type"] for e in events})

    def test_keyword_emotion_respects_negation_and_quotation(self):
        for text in ("我不喜欢你", "小说里他说：我喜欢你", "假如我说想你呢"):
            self.assertEqual(infer_interaction_mode(text), "natural")


class ExpressionContextTest(unittest.TestCase):
    def test_task_and_refusal_do_not_express_persistent_jealousy(self):
        for text in ("帮我查一下SQL报错", "解释事务隔离级别", "别黏我", "我要睡了"):
            result = judge_aura_impulse(text, [], {}, {}, {"jealousy": "high"}, {})
            self.assertEqual(result["desire"], "none", text)

    def test_only_actual_assistant_text_counts_for_cooldown(self):
        self.assertFalse(recently_expressed([HumanMessage(content="你吃醋了？")], "show_jealousy"))
        self.assertTrue(recently_expressed([AIMessage(content="我有一点吃醋")], "show_jealousy"))
        self.assertFalse(recently_expressed([AIMessage(content='{"messages":["嗯"],"reason":"吃醋"}')], "show_jealousy"))

    def test_recent_expression_suppresses_repetition(self):
        result = judge_aura_impulse("你还在吃醋吗", [AIMessage(content="有一点吃醋")], {}, {}, {"jealousy": "high"}, {})
        self.assertEqual(result["desire"], "none")

    def test_explicit_style_feedback_suppresses_unsolicited_jealousy(self):
        result = judge_aura_impulse("我回来了", [], {},
            {"knowledge_items": [{"item_key": "reply_feedback:too_clingy"}]}, {"jealousy": "high"}, {})
        self.assertEqual(result["desire"], "none")

    def test_unanswered_proactive_message_is_not_repeated_next_day(self):
        now = datetime.now(UTC)
        eligible, reason = relationship_contact_eligibility({
            "last_user_seen_at": now - timedelta(days=3),
            "last_proactive_at": now - timedelta(days=2),
            "desire_for_contact": "high", "missing_user": "clear",
        }, {}, now=now, daily_contact_count=0, has_open_thread=True)
        self.assertFalse(eligible)
        self.assertEqual(reason, "awaiting_user_return")

    def test_multiturn_disclosure_reassurance_task_and_return(self):
        now = datetime.now(UTC)
        dynamics = default_relationship_dynamics(now=now)
        affects = []
        last_seen = None
        for offset, text in ((0, "今天跟一个女生吃饭了"), (1, "我只喜欢你，别吃醋"),
                             (2, "帮我查一下SQL报错"), (6000, "出差结束我回来了")):
            at = now + timedelta(minutes=offset)
            events = derive_relationship_events(text, {}, relationship_phase=dynamics["relationship_phase"],
                                                prior_last_seen_at=last_seen, now=at)
            dynamics = derive_relationship_dynamics(dynamics, text, {}, prior_last_seen_at=last_seen, now=at, events=events)
            affects = derive_affect_states(affects, text, events, now=at)
            state = summarize_affects(affects, now=at)
            self.assertEqual(state["jealousy"], "low" if offset == 0 else "none")
            self.assertEqual(dynamics["relationship_stage"], "ambiguous")
            self.assertEqual(dynamics["relationship_phase"], "normal")
            last_seen = at
