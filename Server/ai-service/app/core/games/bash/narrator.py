"""根据已提交的巴什棋局事实生成 Aura 的简短文案。"""

from __future__ import annotations

from typing import Any


def build_bash_game_messages(snapshot: dict[str, Any]) -> list[str]:
    """根据棋局快照生成一到两条自然语言消息。

    Args:
        snapshot: 事务服务返回的公开快照；其中的状态与行动已经提交数据库。

    Returns:
        可直接写入聊天历史和 SSE 的 Aura 文案列表。

    Notes:
        本函数只复述确定性事实，不重新计算落子，也不会调用模型篡改棋局。
    """

    action = snapshot.get("action")
    game = snapshot.get("game") or {}
    new_moves = snapshot.get("newMoves") or []

    if action in {"started", "start_replayed"}:
        return build_start_messages(game, new_moves, replayed=bool(snapshot.get("idempotentReplay")))
    if action in {"moved", "move_replayed"}:
        return build_move_messages(game, new_moves, replayed=bool(snapshot.get("idempotentReplay")))
    if action in {"resigned", "resign_replayed"}:
        return ["好，这局算我赢。石子先放在这儿，想再来一局时叫我。"]
    return [build_status_message(game)]


def build_start_messages(
    game: dict[str, Any],
    new_moves: list[dict[str, Any]],
    *,
    replayed: bool,
) -> list[str]:
    """生成开局或重复开局请求的文案。"""

    if replayed:
        return ["这局已经开好了。" + build_status_message(game)]
    initial = game.get("initialStones")
    max_take = game.get("maxTake")
    if game.get("firstPlayer") == "aura" and new_moves:
        take_count = new_moves[-1].get("takeCount")
        return [
            f"好呀，{initial} 颗石子，每回合拿 1 到 {max_take} 颗。",
            f"我先拿走 {take_count} 颗，现在还剩 {game.get('remainingStones')} 颗，轮到你。",
        ]
    return [f"来。桌上有 {initial} 颗石子，每回合拿 1 到 {max_take} 颗，你先。"]


def build_move_messages(
    game: dict[str, Any],
    new_moves: list[dict[str, Any]],
    *,
    replayed: bool,
) -> list[str]:
    """生成一次用户行动及 Aura 回应后的文案。"""

    if replayed:
        return ["这一步我已经记下了。" + build_status_message(game)]
    user_move = next((move for move in new_moves if move.get("player") == "user"), None)
    aura_move = next((move for move in new_moves if move.get("player") == "aura"), None)
    winner = game.get("winner")
    if winner == "user":
        return [f"你拿走了最后 {user_move.get('takeCount') if user_move else ''} 颗。好吧，这局你赢。"]
    if winner == "aura":
        messages = []
        if user_move:
            messages.append(f"你拿了 {user_move.get('takeCount')} 颗。")
        messages.append(f"我拿走最后 {aura_move.get('takeCount') if aura_move else ''} 颗，这局是我赢。")
        if game.get("difficulty") == "teaching":
            messages.append(
                f"关键是尽量把剩余数量留成 {int(game.get('maxTake', 3)) + 1} 的倍数。"
            )
        return messages

    if aura_move:
        return [
            f"你拿了 {user_move.get('takeCount') if user_move else ''} 颗，"
            f"我拿 {aura_move.get('takeCount')} 颗。还剩 {game.get('remainingStones')} 颗，轮到你。"
        ]
    return [build_status_message(game)]


def build_status_message(game: dict[str, Any]) -> str:
    """把当前剩余数、取子上限和轮次压缩为一句状态说明。"""

    if not game:
        return "现在没有进行中的巴什博弈。"
    if game.get("status") != "active":
        winner = "你" if game.get("winner") == "user" else "我"
        return f"这局已经结束了，{winner}赢。"
    current = "你" if game.get("currentPlayer") == "user" else "我"
    return (
        f"现在还剩 {game.get('remainingStones')} 颗，每回合最多拿 {game.get('maxTake')} 颗，"
        f"轮到{current}。"
    )


def bash_rules_message() -> str:
    """返回当前实现的普通取最后一颗获胜规则说明。"""

    return "规则很简单：桌上先放 15 颗石子，我们轮流拿 1 到 3 颗，拿走最后一颗的人赢。"
