"""Turn-local limits and a conservative memory-write boundary after web access."""

WORLD_TOOLS = {"search_web", "fetch_url"}


def current_turn_calls(state: dict | None) -> list[list[str]]:
    rounds = []
    for message in reversed((state or {}).get("messages", [])):
        role = message.get("role", message.get("type")) if isinstance(message, dict) else getattr(message, "type", None)
        if role in {"human", "user"}:
            break
        calls = message.get("tool_calls", []) if isinstance(message, dict) else getattr(message, "tool_calls", [])
        names = [call.get("name") for call in calls or [] if call.get("name") in WORLD_TOOLS]
        if names:
            rounds.append(names)
    return rounds


def world_turn_finished(state: dict) -> bool:
    # Search + one fetch batch, then synthesize an answer without more tools.
    return len(current_turn_calls(state)) >= 2


def within_world_budget(state: dict | None, name: str) -> bool:
    calls = current_turn_calls(state)
    return len(calls) <= 2 and sum(group.count(name) for group in calls) <= (1 if name == "search_web" else 3)


def world_budget_error() -> dict:
    return {"ok": False, "error": {"code": "tool_budget", "message": "已达到本轮联网预算，请基于已取得的信息回答，缺少的信息如实说明，不再重试。"}}
