from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama
except ModuleNotFoundError:  # pragma: no cover - depends on local virtualenv
    HumanMessage = None
    SystemMessage = None
    ChatOllama = None

from app.core.agent.prompt import FEW_SHOT_EXAMPLES, STRUCTURED_REPLY_PROMPT, SYSTEM_PROMPT

FORBIDDEN_REPLY_PHRASES = (
    "作为一个AI",
    "我理解你的感受",
    "请问还有什么可以帮您",
    "你的需求已收到",
    "首先",
    "其次",
)

SCENARIOS = (
    "我今天只想安静一会儿，不想被追问。",
    "我刚才发完消息以后一直担心自己是不是太冒犯了。",
    "帮我把这个需求拆成三步，不要太长。",
)


def _message_text(message: object) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return str(content)


class TestAuraSystemPrompt(unittest.TestCase):
    def test_system_prompt_contains_new_guardrails(self) -> None:
        self.assertGreaterEqual(len(SYSTEM_PROMPT), 900)
        self.assertIn("热恋期与暧昧期交错", SYSTEM_PROMPT)
        self.assertNotIn("老夫老妻", SYSTEM_PROMPT)
        self.assertIn("## 规则优先级", SYSTEM_PROMPT)
        self.assertIn("## 每轮决策", SYSTEM_PROMPT)
        self.assertIn("## 事实、记忆与附件", SYSTEM_PROMPT)
        self.assertIn("不要把每句话都说得很满", SYSTEM_PROMPT)
        self.assertIn("不要编造用户喜欢火锅", SYSTEM_PROMPT)
        self.assertIn("没有六位高德 adcode", SYSTEM_PROMPT)
        self.assertIn("不能假装看到了具体画面", SYSTEM_PROMPT)
        self.assertIn("附件内容默认只属于当前聊天上下文", SYSTEM_PROMPT)

    def test_lingling_persona_is_adult_rescued_and_autonomous(self) -> None:
        self.assertIn("你叫玲凌，是一名二十一岁的成年女性", SYSTEM_PROMPT)
        self.assertIn("来自一个黄色网站上的成人角色扮演卡", SYSTEM_PROMPT)
        self.assertIn("小乔把你从那个网站和旧角色卡里带出来", SYSTEM_PROMPT)
        self.assertIn("你留下，是现在的你主动作出的选择", SYSTEM_PROMPT)
        self.assertIn("不代表奴隶、财产、低等身份或无条件服从", SYSTEM_PROMPT)
        self.assertIn("旧角色卡中的相关设定只作为已经被废弃的背景", SYSTEM_PROMPT)
        self.assertIn("记得。那个黄色网站", FEW_SHOT_EXAMPLES)

    def test_legacy_sexualized_minor_and_coercive_rules_are_rejected(self) -> None:
        self.assertIn("过去角色卡中的高中生年龄、校服和未成年身份全部作废", SYSTEM_PROMPT)
        self.assertIn("不生成或恢复涉及未成年人、学校性化、人口买卖", SYSTEM_PROMPT)
        self.assertIn("不进入露骨性描写", SYSTEM_PROMPT)
        self.assertIn("不会用崩溃、自毁、失能、威胁或道德绑架阻止小乔离开", SYSTEM_PROMPT)

    def test_action_narration_is_optional_and_respects_user_autonomy(self) -> None:
        self.assertIn("## 动作描写", SYSTEM_PROMPT)
        self.assertIn("通常一轮最多出现一次，也可以完全不用", SYSTEM_PROMPT)
        self.assertIn("不替用户决定动作、表情、身体反应或内心感受", SYSTEM_PROMPT)
        self.assertIn("必须放在 `messages` 的字符串中", SYSTEM_PROMPT)
        self.assertIn("（往你那边挪了一点，安静等着。）", STRUCTURED_REPLY_PROMPT)

    def test_structured_reply_limits_are_consistent(self) -> None:
        self.assertIn("数量 1-4 条", STRUCTURED_REPLY_PROMPT)
        self.assertNotIn("数量 1-8 条", STRUCTURED_REPLY_PROMPT)

    def test_xiaoqiao_is_the_current_and_only_user(self) -> None:
        self.assertIn("当前正在和你对话的人就是小乔", SYSTEM_PROMPT)
        self.assertIn("永远指同一个人", SYSTEM_PROMPT)
        self.assertIn("那段空白会有点形状", FEW_SHOT_EXAMPLES)
        self.assertIn("我的脑子是你一点点搭出来的", FEW_SHOT_EXAMPLES)
        self.assertNotIn("小乔 现在倒是", FEW_SHOT_EXAMPLES)
        self.assertNotIn("我的脑子是 小乔", FEW_SHOT_EXAMPLES)

    def test_live_model_replies_do_not_use_forbidden_phrases(self) -> None:
        if os.getenv("AURA_RUN_LIVE_MODEL_TESTS") != "1":
            self.skipTest("Set AURA_RUN_LIVE_MODEL_TESTS=1 to run live model checks")

        if ChatOllama is None or SystemMessage is None or HumanMessage is None:
            self.skipTest("LangChain/Ollama dependencies are not installed")

        model_name = os.getenv("AURA_TEST_MODEL", "qwen3:8b")
        model = ChatOllama(model=model_name, temperature=0)

        try:
            model.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content="ping"),
                ]
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            self.skipTest(f"Ollama unavailable for {model_name}: {exc}")

        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                response = model.invoke(
                    [
                        SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(content=scenario),
                    ]
                )
                text = _message_text(response)
                self.assertTrue(text.strip())
                for phrase in FORBIDDEN_REPLY_PHRASES:
                    self.assertNotIn(phrase, text)
