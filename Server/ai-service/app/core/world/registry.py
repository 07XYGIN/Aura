"""Resolve the configured provider lazily; an unconfigured tool fails safely."""
import json
import os

from .models import WorldError
from .providers.mcp import MCPWorldProvider
from .service import WorldService


def get_world_service() -> WorldService:
    if os.getenv("WORLD_ENABLED", "false").lower() not in {"true", "1"}:
        raise WorldError("not_configured", "尚未启用外部信息源，当前未取得实时信息。")
    try:
        command = os.getenv("WORLD_MCP_COMMAND") or None
        args = json.loads(os.environ["WORLD_MCP_ARGS"]) if os.getenv("WORLD_MCP_ARGS") else None
        if args is not None and (not isinstance(args, list) or not all(isinstance(arg, str) for arg in args)):
            raise ValueError()
        if command and args is None:
            raise ValueError()
        return WorldService(MCPWorldProvider(command, args))
    except (ValueError, TypeError):
        raise WorldError("configuration_error", "World MCP 配置无效，请检查命令及 JSON 参数列表。") from None
