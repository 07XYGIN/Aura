"""巴什博弈的纯规则与 Aura 落子策略。

本模块不访问数据库、不调用模型，也不依赖 HTTP。相同参数始终产生相同结果，
因此可以独立验证规则，并在请求重试时复现 Aura 的选择。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

BashDifficulty = Literal["serious", "casual", "teaching"]
SUPPORTED_DIFFICULTIES = {"serious", "casual", "teaching"}
MIN_INITIAL_STONES = 5
MAX_INITIAL_STONES = 100
MIN_MAX_TAKE = 1
MAX_MAX_TAKE = 10


class BashRuleError(ValueError):
    """表示棋局配置或一次取子行动违反巴什博弈规则。"""


@dataclass(frozen=True)
class AuraMoveDecision:
    """Aura 的确定性落子结果。

    Attributes:
        take_count: 本回合要拿走的石子数。
        strategy: 写入行动日志的策略标签，用于复盘而不是向用户打分。
    """

    take_count: int
    strategy: str


def validate_bash_rules(initial_stones: int, max_take: int) -> None:
    """校验一局巴什博弈的初始石子数和单回合上限。

    Args:
        initial_stones: 开局石子总数，允许范围为 5 到 100。
        max_take: 每回合最多取走的石子数，允许范围为 1 到 10，且必须
            小于 ``initial_stones``。

    Raises:
        BashRuleError: 任一参数超出范围，或取子上限不小于初始石子数。
    """

    if not MIN_INITIAL_STONES <= initial_stones <= MAX_INITIAL_STONES:
        raise BashRuleError(
            f"初始石子数量必须在 {MIN_INITIAL_STONES} 到 {MAX_INITIAL_STONES} 之间"
        )
    if not MIN_MAX_TAKE <= max_take <= MAX_MAX_TAKE:
        raise BashRuleError(
            f"每回合最多取走的石子数必须在 {MIN_MAX_TAKE} 到 {MAX_MAX_TAKE} 之间"
        )
    if max_take >= initial_stones:
        raise BashRuleError("每回合取子上限必须小于初始石子数量")


def legal_take_limit(remaining_stones: int, max_take: int) -> int:
    """返回当前局面允许取走的最大石子数。

    Args:
        remaining_stones: 行动前剩余的石子数。
        max_take: 本局约定的单回合取子上限。

    Returns:
        ``remaining_stones`` 与 ``max_take`` 中较小的正整数。

    Raises:
        BashRuleError: 棋局已经没有剩余石子，或取子上限不是正数。
    """

    if remaining_stones <= 0:
        raise BashRuleError("棋局已经结束，不能继续取石子")
    if max_take <= 0:
        raise BashRuleError("每回合取子上限必须大于 0")
    return min(remaining_stones, max_take)


def apply_take(remaining_stones: int, take_count: int, max_take: int) -> int:
    """校验并应用一次取子行动。

    Args:
        remaining_stones: 行动前剩余石子数。
        take_count: 当前玩家希望拿走的石子数。
        max_take: 本局单回合取子上限。

    Returns:
        行动后的剩余石子数；返回 0 表示当前行动者获胜。

    Raises:
        BashRuleError: 取子数小于 1、超过单回合上限或超过当前剩余数。
    """

    limit = legal_take_limit(remaining_stones, max_take)
    if take_count < 1:
        raise BashRuleError("每回合至少要拿走 1 颗石子")
    if take_count > limit:
        raise BashRuleError(f"这一回合最多只能拿走 {limit} 颗石子")
    return remaining_stones - take_count


def winning_take_count(remaining_stones: int, max_take: int) -> int | None:
    """计算能把对手留在必败位的取子数。

    对普通取最后一颗获胜的巴什博弈，``max_take + 1`` 的倍数是当前行动方
    的必败位。若当前局面可以一步控制到该倍数，返回对应取子数；已经位于
    必败位时返回 ``None``。
    """

    limit = legal_take_limit(remaining_stones, max_take)
    remainder = remaining_stones % (max_take + 1)
    if remainder == 0:
        return None
    return min(remainder, limit)


def choose_aura_take(
    remaining_stones: int,
    max_take: int,
    difficulty: BashDifficulty,
    decision_key: str,
) -> AuraMoveDecision:
    """根据难度和稳定决策键选择 Aura 的合法取子数。

    Args:
        remaining_stones: Aura 行动前剩余石子数。
        max_take: 本局单回合取子上限。
        difficulty: ``serious`` 始终采取最优策略；``teaching`` 同样最优，
            但解释延迟到终局；``casual`` 约 65% 采用最优策略，其余选择
            一个确定性的非最优合法行动。
        decision_key: 用于 casual 模式稳定采样的非空字符串，通常由棋局 ID、
            版本和回合号组成。同一键重试时必须得到同一行动。

    Returns:
        包含合法取子数和策略标签的不可变决定。

    Raises:
        BashRuleError: 难度不受支持、决策键为空或当前棋局已经结束。
    """

    if difficulty not in SUPPORTED_DIFFICULTIES:
        raise BashRuleError("游戏难度必须是 serious、casual 或 teaching")
    if not decision_key:
        raise BashRuleError("Aura 落子缺少稳定决策键")

    limit = legal_take_limit(remaining_stones, max_take)
    winning_take = winning_take_count(remaining_stones, max_take)
    optimal_take = winning_take or 1
    optimal_strategy = "control" if winning_take else "forced_position"

    if difficulty in {"serious", "teaching"} or limit == 1:
        return AuraMoveDecision(optimal_take, optimal_strategy)

    digest = hashlib.sha256(decision_key.encode("utf-8")).digest()
    use_optimal = digest[0] < 166  # 166 / 256，约为 65%。
    alternatives = [take for take in range(1, limit + 1) if take != optimal_take]
    if use_optimal or not alternatives:
        return AuraMoveDecision(optimal_take, "casual_control")

    alternative = alternatives[digest[1] % len(alternatives)]
    return AuraMoveDecision(alternative, "casual_experiment")
