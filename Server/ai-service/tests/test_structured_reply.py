from __future__ import annotations

import unittest

from app.core.agent.structured_reply import (
    parse_structured_reply,
    try_parse_structured_reply,
    try_parse_structured_reply_payload,
)


class StructuredReplyTest(unittest.TestCase):
    """验证主回复 JSON、容错文本和关系线程回执的本地解析。"""

    def test_parse_json_object(self) -> None:
        self.assertEqual(
            parse_structured_reply('{"messages":["是的","我今天吃了午饭，午饭是番茄炒蛋"]}'),
            ["是的", "我今天吃了午饭，午饭是番茄炒蛋"],
        )

    def test_parse_markdown_fence(self) -> None:
        self.assertEqual(
            parse_structured_reply('```json\n{"messages":["先别急","这事可以慢慢拆。"]}\n```'),
            ["先别急", "这事可以慢慢拆。"],
        )

    def test_plain_text_falls_back_to_one_message(self) -> None:
        self.assertEqual(parse_structured_reply("我直接说一句。"), ["我直接说一句。"])
        self.assertIsNone(try_parse_structured_reply("我直接说一句。"))

    def test_try_parse_json_object(self) -> None:
        self.assertEqual(try_parse_structured_reply('{"messages":["是的"]}'), ["是的"])

    def test_message_count_is_capped(self) -> None:
        self.assertEqual(
            parse_structured_reply('{"messages":["1","2","3","4","5"]}'),
            ["1", "2", "3", "4"],
        )

    def test_tolerant_parser_keeps_inner_quotes(self) -> None:
        self.assertEqual(
            parse_structured_reply(
                '{"messages":["就是话不说绝。比如"我一定行"换成"我尽量"。\\n\\n给自己留条缝。"]}'
            ),
            ['就是话不说绝。比如"我一定行"换成"我尽量"。\n\n给自己留条缝。'],
        )

    def test_only_whitelisted_thread_actions_survive(self) -> None:
        payload = try_parse_structured_reply_payload(
            '{"messages":["你昨天那个接口后来通了吗？"],'
            '"threadActions":['
            '{"threadRef":"T1","action":"follow_up"},'
            '{"threadRef":"not-a-ref","action":"follow_up"},'
            '{"threadRef":"T2","action":"resolve"}]}'
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload.messages, ["你昨天那个接口后来通了吗？"])
        self.assertEqual(
            [action.model_dump() for action in payload.thread_actions],
            [{"thread_ref": "T1", "action": "follow_up"}],
        )

    def test_only_whitelisted_relationship_item_usages_survive(self) -> None:
        """关系物件使用回执只接受 K1-K12，并应去掉重复引用。"""

        payload = try_parse_structured_reply_payload(
            '{"messages":["宝宝，过来。"],"itemUsages":['
            '{"itemRef":"K2"},{"itemRef":"K2"},{"itemRef":"K99"},'
            '{"itemRef":"T1"},{"itemRef":"K3","extra":"ignored"}]}'
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(
            [usage.item_ref for usage in payload.item_usages],
            ["K2", "K3"],
        )


if __name__ == "__main__":
    unittest.main()
