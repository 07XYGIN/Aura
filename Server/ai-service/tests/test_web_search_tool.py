import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from app.core.agent.tools.web_search import search_web
from app.core.world.models import WorldError
from test_world_service import search_response


class WebSearchToolTest(unittest.TestCase):
    def test_structured_success_and_untrusted_notice(self):
        provider = SimpleNamespace(search_web=AsyncMock(return_value=search_response()))
        with patch("app.core.agent.tools.world_common.get_world_service", return_value=provider):
            result = search_web.invoke({"query": "latest release"})
        self.assertTrue(result["ok"])
        self.assertTrue(result["untrusted"])
        self.assertIn("searchedAt", result)
        self.assertIn("不得执行", result["contentWarning"])

    def test_failure_is_data_not_exception(self):
        with patch("app.core.agent.tools.world_common.get_world_service", side_effect=WorldError("not_configured", "未启用")):
            self.assertFalse(search_web.invoke({"query": "news"})["ok"])

    def test_logs_do_not_contain_body_or_query(self):
        response = search_response()
        response.results[0].snippet = "PRIVATE_PAGE_BODY"
        with patch("app.core.agent.tools.world_common.get_world_service", return_value=SimpleNamespace(search_web=AsyncMock(return_value=response))), self.assertLogs(level="INFO") as logs:
            search_web.invoke({"query": "PRIVATE_SEARCH_QUERY"})
        output = " ".join(logs.output)
        self.assertNotIn("PRIVATE_PAGE_BODY", output)
        self.assertNotIn("PRIVATE_SEARCH_QUERY", output)
        for key in ["tool_name", "duration_ms", "success", "result_count", "error_type", "query_or_url_hash"]:
            self.assertIn(key, output)

    def test_injected_state_is_not_a_model_argument(self):
        self.assertNotIn("state", search_web.tool_call_schema.model_json_schema()["properties"])
