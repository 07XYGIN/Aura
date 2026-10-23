"""Compatibility exports backed by the versioned prompt builder."""

from .prompt_builder import PromptBuilder


PROMPT_VERSION = "v1"
PROMPTS = PromptBuilder(PROMPT_VERSION)

SYSTEM_PROMPT = PROMPTS.build_system()
STRUCTURED_REPLY_PROMPT = PROMPTS.build_output_contract()
FEW_SHOT_EXAMPLES = PROMPTS.build_few_shot()
MEMORY_PROMPT = PROMPTS.build_memory()

__all__ = [
    "FEW_SHOT_EXAMPLES",
    "MEMORY_PROMPT",
    "PROMPTS",
    "PROMPT_VERSION",
    "STRUCTURED_REPLY_PROMPT",
    "SYSTEM_PROMPT",
]
