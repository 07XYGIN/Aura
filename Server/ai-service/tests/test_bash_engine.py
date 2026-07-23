from __future__ import annotations

import unittest

from app.core.games.bash.engine import (
    BashRuleError,
    apply_take,
    choose_aura_take,
    legal_take_limit,
    validate_bash_rules,
    winning_take_count,
)


class BashEngineTest(unittest.TestCase):
    """验证巴什博弈纯规则和 Aura 稳定策略。"""

    def test_validate_rules_accepts_default_game(self) -> None:
        """默认 15 颗、每轮最多 3 颗应是合法配置。"""

        validate_bash_rules(15, 3)

    def test_validate_rules_rejects_out_of_range_values(self) -> None:
        """初始数量和取子上限越界时应给出领域错误。"""

        for initial, max_take in ((4, 3), (101, 3), (15, 0), (15, 11), (5, 5)):
            with self.subTest(initial=initial, max_take=max_take):
                with self.assertRaises(BashRuleError):
                    validate_bash_rules(initial, max_take)

    def test_apply_take_accepts_legal_moves_and_detects_winner(self) -> None:
        """合法行动应准确减少石子，拿走最后一颗时返回零。"""

        self.assertEqual(apply_take(15, 1, 3), 14)
        self.assertEqual(apply_take(15, 3, 3), 12)
        self.assertEqual(apply_take(2, 2, 3), 0)

    def test_apply_take_rejects_zero_limit_and_overdraw(self) -> None:
        """零颗、超过上限、超过剩余和终局后行动都必须被拒绝。"""

        for remaining, take_count, max_take in ((10, 0, 3), (10, 4, 3), (2, 3, 3), (0, 1, 3)):
            with self.subTest(remaining=remaining, take_count=take_count):
                with self.assertRaises(BashRuleError):
                    apply_take(remaining, take_count, max_take)

    def test_legal_take_limit_never_exceeds_remaining(self) -> None:
        """临近终局时合法上限应收缩到剩余石子数。"""

        self.assertEqual(legal_take_limit(2, 3), 2)

    def test_winning_take_leaves_multiple_of_four(self) -> None:
        """默认规则下可控局面应留下四的倍数，必败位返回空。"""

        self.assertEqual(winning_take_count(15, 3), 3)
        self.assertEqual(winning_take_count(14, 3), 2)
        self.assertEqual(winning_take_count(13, 3), 1)
        self.assertIsNone(winning_take_count(12, 3))

    def test_serious_strategy_is_legal_for_every_position(self) -> None:
        """认真模式在所有非终局剩余数下都必须给出合法行动。"""

        for remaining in range(1, 31):
            decision = choose_aura_take(remaining, 3, "serious", f"serious-{remaining}")
            self.assertGreaterEqual(decision.take_count, 1)
            self.assertLessEqual(decision.take_count, min(remaining, 3))

    def test_casual_strategy_is_stable_for_retries(self) -> None:
        """相同稳定键重复计算时必须返回完全相同的 casual 决定。"""

        first = choose_aura_take(14, 3, "casual", "same-game-version-turn")
        second = choose_aura_take(14, 3, "casual", "same-game-version-turn")
        self.assertEqual(first, second)

    def test_casual_strategy_has_reproducible_non_optimal_cases(self) -> None:
        """一组稳定键中应存在可复现的非最优行动，而不是伪装成认真模式。"""

        decisions = [
            choose_aura_take(14, 3, "casual", f"casual-{index}")
            for index in range(100)
        ]
        self.assertTrue(any(item.strategy == "casual_experiment" for item in decisions))


if __name__ == "__main__":
    unittest.main()
