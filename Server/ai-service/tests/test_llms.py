import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import llms
from app.core.owned_llms import DEEPSEEK


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


if __name__ == "__main__":
    unittest.main()
