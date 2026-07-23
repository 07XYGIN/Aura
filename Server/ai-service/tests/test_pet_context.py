from __future__ import annotations

import unittest

from app.core.pet.context import NO_PET_CONTEXT, format_pet_context, load_pet_context_sync


class PetContextTest(unittest.TestCase):
    """验证普通聊天只接收真实、无分数和无虚构的宠物上下文。"""

    def test_invalid_user_id_returns_explicit_no_pet_constraint(self) -> None:
        """无法查询所有者时不得假装存在宠物。"""

        self.assertEqual(load_pet_context_sync("not-a-uuid"), NO_PET_CONTEXT)
        self.assertIn("不要假装", NO_PET_CONTEXT)

    def test_context_uses_natural_labels_and_persisted_events(self) -> None:
        """上下文应包含自然状态和已记录事件，不包含内部照顾分数。"""

        context = format_pet_context(
            name="团子",
            species="cat",
            personality="gentle",
            natural_state={
                "satiety": "吃得很饱",
                "energy": "精神很好",
                "cleanliness": "毛发很整洁",
                "activity": "idle",
                "mood": "calm",
                "growthStage": "baby",
            },
            recent_narratives=["团子刚刚吃完东西。"],
        )
        self.assertIn("团子", context)
        self.assertIn("团子刚刚吃完东西", context)
        self.assertNotIn("80", context)
        self.assertNotIn("亲密度", context)
        self.assertIn("不要虚构", context)


if __name__ == "__main__":
    unittest.main()
