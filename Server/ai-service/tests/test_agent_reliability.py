from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.reliability import invoke_model_with_retry


class ClientError(RuntimeError):
    status_code = 400


class AgentReliabilityTest(unittest.TestCase):
    def test_retries_transient_model_error_then_returns_response(self) -> None:
        invoke = Mock(side_effect=[TimeoutError("temporary"), "ok"])
        sleep = Mock()

        with patch("app.core.agent.reliability.model_max_attempts", return_value=2):
            result = invoke_model_with_retry(invoke, ["message"], operation="test", sleep=sleep)

        self.assertEqual(result, "ok")
        self.assertEqual(invoke.call_count, 2)
        sleep.assert_called_once()

    def test_does_not_retry_invalid_client_request(self) -> None:
        invoke = Mock(side_effect=ClientError("bad request"))

        with patch("app.core.agent.reliability.model_max_attempts", return_value=3):
            with self.assertRaises(ClientError):
                invoke_model_with_retry(invoke, ["message"], operation="test", sleep=Mock())

        self.assertEqual(invoke.call_count, 1)


if __name__ == "__main__":
    unittest.main()
