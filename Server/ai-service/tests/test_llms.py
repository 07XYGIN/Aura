import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import llms
from app.core.owned_llms import DEEPSEEK, QWEN_3_7_PLUS


class LlmSamplingConfigTest(unittest.TestCase):
    def test_create_llm_passes_supported_sampling_parameters(self):
        with patch.object(llms, "ChatOpenAI") as chat_openai:
            llms.create_llm(
                DEEPSEEK,
                temperature=0.75,
                top_p=0.9,
                streaming=True,
            )

        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["temperature"], 0.75)
        self.assertEqual(kwargs["top_p"], 0.9)
        self.assertTrue(kwargs["streaming"])
        self.assertNotIn("top_k", kwargs)

    def test_float_env_falls_back_and_clamps(self):
        with patch.dict("os.environ", {"TEST_SAMPLE": "invalid"}):
            self.assertEqual(llms.float_env("TEST_SAMPLE", 0.75, 0.0, 2.0), 0.75)
        with patch.dict("os.environ", {"TEST_SAMPLE": "3.5"}):
            self.assertEqual(llms.float_env("TEST_SAMPLE", 0.75, 0.0, 2.0), 2.0)
        with patch.dict("os.environ", {"TEST_SAMPLE": "-0.2"}):
            self.assertEqual(llms.float_env("TEST_SAMPLE", 0.75, 0.0, 1.0), 0.0)

    def test_qwen_uses_json_mode_without_thinking(self):
        with patch.object(llms, "ChatOpenAI") as chat_openai:
            llms.create_llm(
                QWEN_3_7_PLUS,
                temperature=0,
                top_p=0.2,
                json_mode=True,
                thinking_enabled=True,
            )

        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], "qwen3.7-plus")
        self.assertEqual(kwargs["model_kwargs"], {"response_format": {"type": "json_object"}})
        self.assertEqual(kwargs["extra_body"], {"enable_thinking": False})

    def test_qwen_chat_keeps_tool_calling_outside_strict_json_mode(self):
        with patch.object(llms, "ChatOpenAI") as chat_openai:
            llms.create_llm(
                QWEN_3_7_PLUS,
                temperature=0.7,
                top_p=0.85,
                streaming=True,
            )

        kwargs = chat_openai.call_args.kwargs
        self.assertNotIn("model_kwargs", kwargs)
        self.assertEqual(kwargs["extra_body"], {"enable_thinking": False})

    def test_aura_defaults_to_qwen_for_every_task(self):
        self.assertIs(llms.CHAT_MODEL, QWEN_3_7_PLUS)
        self.assertIs(llms.STRUCTURED_REPLY_MODEL, QWEN_3_7_PLUS)
        self.assertIs(llms.MEMORY_JUDGE_MODEL, QWEN_3_7_PLUS)
        self.assertIs(llms.EMOTION_JUDGE_MODEL, QWEN_3_7_PLUS)


if __name__ == "__main__":
    unittest.main()
