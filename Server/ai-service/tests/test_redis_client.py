import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import redis_client


class RedisClientTest(unittest.TestCase):
    def tearDown(self):
        redis_client.get_redis_client.cache_clear()

    def test_get_redis_client_uses_resp2_for_redis_5_compatibility(self):
        redis_client.get_redis_client.cache_clear()

        with patch("app.core.redis_client.Redis.from_url", return_value=object()) as from_url:
            redis_client.get_redis_client()

        _, kwargs = from_url.call_args
        self.assertEqual(kwargs["protocol"], 2)
        self.assertTrue(kwargs["decode_responses"])


if __name__ == "__main__":
    unittest.main()
