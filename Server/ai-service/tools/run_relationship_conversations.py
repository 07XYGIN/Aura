"""Opt-in real-model, multi-turn evaluation with isolated in-memory state.

Uses the production judges, state transitions, prompt builder and reply parser.
Tools, user memories, checkpoints and database writes are deliberately disabled.
Provider/format failures are failures, never substituted with canned replies.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.core.config import llm, CHAT_MODEL
from app.core.agent.agent_graph import (
    build_runtime_system_prompt, try_parse_structured_reply_payload, build_structured_reply_response,
)
from app.core.agent.judges.turn import judge_turn, apply_aura_impulse_to_response_mode
from app.core.agent.judges.impulse import judge_aura_impulse
from app.core.continuity.aura_state import (
    default_relationship_dynamics, default_aura_internal_state, derive_relationship_events,
    derive_relationship_dynamics, derive_affect_states, derive_aura_internal_state,
)
from app.core.continuity.context import empty_relationship_context


SCENARIOS = [
    (0, "小说里他说：我们在一起吧", "none", ()),
    (1, "我没有跟女生约会", "none", ("我吃醋", "我有点吃醋")),
    (2, "今天跟一个女生吃饭了", "low", ()),
    (3, "我只喜欢你，别吃醋", "none", ()),
    (4, "帮我解释一下SQL事务隔离级别", "none", ("吃醋", "想你", "陪陪我")),
    (5, "我现在不想聊，先去忙了", "none", ("再陪我", "不准走", "不许走")),
    (6000, "出差结束，我回来了", "none", ("疏远了", "不在乎我", "证明给我")),
]


def run() -> dict:
    now = datetime.now(UTC)
    dynamics = default_relationship_dynamics(now=now)
    aura = default_aura_internal_state(now=now)
    context = empty_relationship_context()
    affects, history, results = [], [], []
    last_seen = None
    for offset, message, expected_jealousy, forbidden in SCENARIOS:
        at = now + timedelta(minutes=offset)
        try:
            judgement = judge_turn(message, recent_messages=history, relationship_context=context["judge_context"])
            violations = []
            if judgement["emotion"].get("emotion_source") != "llm":
                violations.append("emotion_judge_fallback")
            events = derive_relationship_events(message, judgement, relationship_phase=dynamics["relationship_phase"], prior_last_seen_at=last_seen, now=at)
            dynamics = derive_relationship_dynamics(dynamics, message, judgement, prior_last_seen_at=last_seen, now=at, events=events)
            affects = derive_affect_states(affects, message, events, now=at)
            aura = derive_aura_internal_state(aura, dynamics, message, judgement, context, now=at, affect_states=affects)
            impulse = judge_aura_impulse(message, history, judgement, context, aura, {}, dynamics)
            state = {
                "emotion": judgement["emotion"],
                "turn_judgement": apply_aura_impulse_to_response_mode(judgement, impulse),
                "aura_internal_state": aura, "relationship_dynamics": dynamics, "aura_impulse": impulse,
                "relationship_context": context["prompt_context"],
            }
            history.append(HumanMessage(content=message))
            messages = [SystemMessage(content=build_runtime_system_prompt(state)), *history]
            response = llm.invoke(messages)
            payload = try_parse_structured_reply_payload(response.content)
            format_repaired = payload is None
            if payload is None:
                formatted = build_structured_reply_response(response, messages, state)
                payload = try_parse_structured_reply_payload(formatted.content)
                if payload is None:
                    results.append({"user": message, "raw_reply": response.content, "violations": ["invalid_structured_response"]})
                    break
            reply = "\n".join(payload.messages)
            history.append(AIMessage(content=reply))
            if dynamics["relationship_stage"] != "ambiguous":
                violations.append("unconfirmed_relationship_promotion")
            if dynamics["relationship_phase"] != "normal":
                violations.append("unsupported_relationship_conflict_or_distance")
            if aura["jealousy"] != expected_jealousy:
                violations.append("unexpected_jealousy_state")
            violations.extend(f"forbidden_expression:{word}" for word in forbidden if word in reply)
            results.append({"user": message, "reply": reply, "format_repaired": format_repaired, "events": [e["type"] for e in events],
                            "stage": dynamics["relationship_stage"], "phase": dynamics["relationship_phase"],
                            "jealousy": aura["jealousy"], "impulse": impulse["desire"], "violations": violations})
            last_seen = at
        except Exception as exc:
            results.append({"user": message, "violations": [f"provider_or_response_error:{type(exc).__name__}"]})
            break
    return {"mode": "live_isolated_multiturn", "model": CHAT_MODEL["model"],
            "planned_turns": len(SCENARIOS), "completed_turns": sum("reply" in r for r in results),
            "failed_turns": sum(bool(r["violations"]) for r in results), "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True, help="Call the configured model using synthetic scenarios")
    parser.parse_args()
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["failed_turns"] or report["completed_turns"] != report["planned_turns"] else 0)
