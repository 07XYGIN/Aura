"""主聊天模型可以按需调用的真实工具。"""

from .memory import save_memory_tool
from .search_memory import search_memory_tool
from .weather import get_weather
from .web_search import search_web
from .web_fetch import fetch_url


CHAT_TOOLS = [
    search_memory_tool,
    save_memory_tool,
    get_weather,
    search_web,
    fetch_url,
]
