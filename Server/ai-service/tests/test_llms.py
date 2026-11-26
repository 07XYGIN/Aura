import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import llms


QWEN = llms.get_llm("qwen")


class LlmRegistryTest(unittest.TestCase):
    def test_registry_names_are_unique_and_ordered(self):
        names = llms.list_llm_names()
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[0], "qwen")
        self.assertEqual(names, tuple(config["llm_name"] for config in llms.LLM_DICT))

    def test_registry_entries_carry_required_fields(self):
        for config in llms.LLM_DICT:
            with self.subTest(llm=config["llm_name"]):
                self.assertTrue(config["model"])
                self.assertTrue(config["base_url"].startswith("https://"))
                self.assertTrue(config["api_key_env"].isupper())
                self.assertNotIn("sk-", config["base_url"])

    def test_get_llm_rejects_unknown_name(self):
        with self.assertRaises(KeyError):
            llms.get_llm("not-a-model")

    def test_duplicate_names_fail_fast(self):
        with self.assertRaises(ValueError):
            llms._index_registry([dict(QWEN), dict(QWEN)])

    def test_availability_reports_missing_keys(self):
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "configured"}, clear=False):
            self.assertTrue(llms.llm_availability()["qwen"])


class LlmSamplingConfigTest(unittest.TestCase):
    def test_create_llm_passes_supported_sampling_parameters(self):
        with patch.object(llms, "ChatOpenAI") as chat_openai:
            llms.create_llm(
                QWEN,
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
                QWEN,
                temperature=0,
                top_p=0.2,
                json_mode=True,
                thinking_enabled=True,
            )

        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], "qwen3.8-max")
        self.assertEqual(kwargs["model_kwargs"], {"response_format": {"type": "json_object"}})
        self.assertEqual(kwargs["extra_body"], {"enable_thinking": False})

    def test_qwen_chat_keeps_tool_calling_outside_strict_json_mode(self):
        with patch.object(llms, "ChatOpenAI") as chat_openai:
            llms.create_llm(
                QWEN,
                temperature=0.7,
                top_p=0.85,
                streaming=True,
            )

        kwargs = chat_openai.call_args.kwargs
        self.assertNotIn("model_kwargs", kwargs)
        self.assertEqual(kwargs["extra_body"], {"enable_thinking": False})

    def test_provider_without_thinking_support_gets_no_qwen_extension(self):
        deepseek = llms.get_llm("deepseek")
        with patch.object(llms, "ChatOpenAI") as chat_openai:
            llms.create_llm(deepseek, json_mode=True, thinking_enabled=True)

        kwargs = chat_openai.call_args.kwargs
        self.assertNotIn("extra_body", kwargs)
        self.assertEqual(kwargs["model_kwargs"], {"response_format": {"type": "json_object"}})

    def test_aura_defaults_to_qwen_for_every_task(self):
        self.assertIs(llms.CHAT_MODEL, QWEN)
        self.assertIs(llms.STRUCTURED_REPLY_MODEL, QWEN)
        self.assertIs(llms.MEMORY_JUDGE_MODEL, QWEN)
        self.assertIs(llms.EMOTION_JUDGE_MODEL, QWEN)


if __name__ == "__main__":
    unittest.main()
