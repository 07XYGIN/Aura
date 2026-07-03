from app.core.agent.structured_reply import parse_structured_reply


def test_parse_structured_reply_json_object():
    assert parse_structured_reply('{"messages":["是的","我今天吃了午饭，午饭是番茄炒蛋"]}') == [
        "是的",
        "我今天吃了午饭，午饭是番茄炒蛋",
    ]


def test_parse_structured_reply_markdown_fence():
    assert parse_structured_reply('```json\n{"messages":["先别急","这事可以慢慢拆。"]}\n```') == [
        "先别急",
        "这事可以慢慢拆。",
    ]


def test_parse_structured_reply_plain_text_fallback():
    assert parse_structured_reply("我直接说一句。") == ["我直接说一句。"]


def test_parse_structured_reply_caps_message_count():
    assert parse_structured_reply('{"messages":["1","2","3","4","5"]}') == ["1", "2", "3", "4"]
