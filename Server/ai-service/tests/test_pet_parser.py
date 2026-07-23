from __future__ import annotations

import unittest

from app.core.pet.parser import parse_pet_chat_intent


class PetParserTest(unittest.TestCase):
    """验证宠物命令的中文解析与普通亲密对话隔离。"""

    def test_adoption_extracts_species_and_name(self) -> None:
        """明确的领养句应提取标准物种和宠物名字。"""

        intent = parse_pet_chat_intent("我们领养一只小猫，叫团子", has_pet=False)
        self.assertEqual(intent.action, "adopt")
        self.assertEqual(intent.species, "cat")
        self.assertEqual(intent.name, "团子")

    def test_adoption_without_name_requests_more_information(self) -> None:
        """只有领养意愿但没有名字时应进入追问，不擅自创建默认宠物。"""

        intent = parse_pet_chat_intent("我们领养宠物吧", has_pet=False)
        self.assertEqual(intent.action, "adopt_prompt")

    def test_pet_actions_require_existing_pet_and_pet_marker(self) -> None:
        """“摸摸”不能截获情侣对话，明确“摸摸宠物”且已有宠物才命中。"""

        self.assertIsNone(parse_pet_chat_intent("摸摸", has_pet=True))
        self.assertIsNone(parse_pet_chat_intent("摸摸宠物", has_pet=False))
        self.assertEqual(parse_pet_chat_intent("摸摸宠物", has_pet=True).action, "pet")

    def test_specific_actions_do_not_get_misclassified_as_play(self) -> None:
        """陪宠物梳毛和哄宠物睡觉应保持各自具体动作。"""

        self.assertEqual(parse_pet_chat_intent("陪宠物梳毛", has_pet=True).action, "groom")
        self.assertEqual(parse_pet_chat_intent("哄宠物睡觉", has_pet=True).action, "sleep")
        self.assertEqual(parse_pet_chat_intent("陪宠物玩一会", has_pet=True).action, "play")

    def test_rename_extracts_new_name_only_when_pet_exists(self) -> None:
        """改名必须已有宠物，并提取新的合法名字。"""

        self.assertIsNone(parse_pet_chat_intent("给宠物改名叫糯米", has_pet=False))
        intent = parse_pet_chat_intent("给宠物改名叫糯米", has_pet=True)
        self.assertEqual(intent.action, "rename")
        self.assertEqual(intent.name, "糯米")

    def test_action_can_address_the_persisted_pet_name(self) -> None:
        """传入真实宠物名后可以识别“摸摸团子”，但未知名字仍不命中。"""

        self.assertEqual(
            parse_pet_chat_intent("摸摸团子", has_pet=True, pet_name="团子").action,
            "pet",
        )
        self.assertIsNone(
            parse_pet_chat_intent("摸摸小白", has_pet=True, pet_name="团子")
        )

    def test_negated_or_hypothetical_commands_never_mutate_pet(self) -> None:
        """否定和假设语句必须留给主对话，不能执行领养或照顾动作。"""

        examples = (
            "我不想养一只猫叫团子",
            "别给宠物洗澡",
            "它不需要睡觉",
            "不要摸摸团子",
            "如果以后养一只猫叫团子会怎样",
        )
        for message in examples:
            with self.subTest(message=message):
                self.assertIsNone(
                    parse_pet_chat_intent(message, has_pet=True, pet_name="团子")
                )

    def test_unrelated_rename_sentences_are_not_pet_commands(self) -> None:
        """项目、Aura 和变量改名不能误改共同宠物名字。"""

        examples = (
            "把项目改名叫Aura",
            "我想给你改名叫宝宝",
            "这个变量名字改成pet_id",
        )
        for message in examples:
            with self.subTest(message=message):
                self.assertIsNone(
                    parse_pet_chat_intent(message, has_pet=True, pet_name="团子")
                )


if __name__ == "__main__":
    unittest.main()
