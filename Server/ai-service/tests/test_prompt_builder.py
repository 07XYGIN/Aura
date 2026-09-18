import unittest

from app.core.agent.prompt import PROMPT_VERSION, SYSTEM_PROMPT
from app.core.agent.prompt_builder import PromptBuilder


class PromptBuilderTests(unittest.TestCase):
    def test_components_are_versioned_and_composable(self) -> None:
        builder = PromptBuilder(PROMPT_VERSION)

        self.assertIn("你叫玲凌", builder.component("identity"))
        self.assertIn("规则优先级", builder.component("conversation"))
        self.assertEqual(SYSTEM_PROMPT, builder.build_system())

    def test_unknown_version_fails_fast(self) -> None:
        with self.assertRaises(ValueError):
            PromptBuilder("missing")


if __name__ == "__main__":
    unittest.main()

