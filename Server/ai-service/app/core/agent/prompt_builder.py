"""Composable, versioned prompt loading with an explicit component order."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


PROMPT_ROOT = Path(__file__).with_name("prompts")


class PromptBuilder:
    SYSTEM_COMPONENTS = ("identity", "relationship", "conversation", "world", "safety")

    def __init__(self, version: str = "v1") -> None:
        version_path = PROMPT_ROOT / version
        if not version_path.is_dir():
            raise ValueError(f"unknown prompt version: {version}")
        self.version = version
        self.version_path = version_path

    @lru_cache(maxsize=32)
    def component(self, name: str) -> str:
        path = self.version_path / f"{name}.md"
        if not path.is_file():
            raise ValueError(f"unknown prompt component: {name}")
        return path.read_text(encoding="utf-8").strip()

    def compose(self, *names: str) -> str:
        return "\n\n".join(self.component(name) for name in names).strip()

    def build_system(self) -> str:
        return self.compose(*self.SYSTEM_COMPONENTS)

    def build_conversation(self) -> str:
        return self.compose(*self.SYSTEM_COMPONENTS, "few_shot", "output_contract")

    def build_output_contract(self) -> str:
        return self.component("output_contract")

    def build_few_shot(self) -> str:
        return self.component("few_shot")

    def build_memory(self) -> str:
        return self.component("memory")
