import unittest
from fnmatch import fnmatch
from unittest.mock import patch

from app.core import silence_state


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    def set(self, key, value):
        self.values[key] = str(value)
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)

    def scan_iter(self, match):
        return [key for key in self.values if fnmatch(key, match)]


class SilenceStateTest(unittest.TestCase):
    def test_record_user_message_activity_updates_last_time_and_resets_trigger(self):
        redis = FakeRedis()
        redis.set(silence_state.proactive_triggered_key("user-1"), "1")

        with patch("app.core.silence_state.get_redis_client", return_value=redis):
            stored = silence_state.record_user_message_activity("user-1", timestamp=123.5)

        self.assertTrue(stored)
        self.assertEqual(redis.get(silence_state.last_user_message_key("user-1")), "123.5")
        self.assertIsNone(redis.get(silence_state.proactive_triggered_key("user-1")))

    def test_list_tracked_silence_user_ids_reads_last_message_keys(self):
        redis = FakeRedis()
        redis.set(silence_state.last_user_message_key("user-1"), "1")
        redis.set(silence_state.last_user_message_key("user-2"), "2")
        redis.set(silence_state.proactive_triggered_key("user-3"), "1")

        with patch("app.core.silence_state.get_redis_client", return_value=redis):
            user_ids = silence_state.list_tracked_silence_user_ids()

        self.assertEqual(user_ids, ["user-1", "user-2"])


if __name__ == "__main__":
    unittest.main()
