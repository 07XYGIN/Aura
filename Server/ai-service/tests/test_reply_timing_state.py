import unittest
from unittest.mock import patch

from app.core.reply_timing_state import pending_bubbles_key, store_reply_timing_state


class ReplyTimingStateTest(unittest.TestCase):
    def test_store_reply_timing_state_writes_pending_bubbles_payload(self):
        reply_batch = {
            "turn_id": "turn-1",
            "batch_id": "batch-1",
            "messages": [
                {
                    "message_id": "msg-1",
                    "content": "是的",
                    "delay_ms": 500,
                    "sent_at": "2026-07-04T10:00:00+00:00",
                },
                {
                    "message_id": "msg-2",
                    "content": "我知道了。",
                    "delay_ms": 800,
                    "sent_at": "2026-07-04T10:00:01+00:00",
                },
            ],
        }

        with patch("app.core.reply_timing_state.set_json", return_value=True) as set_json:
            stored = store_reply_timing_state("user-1", reply_batch)

        self.assertTrue(stored)
        key, payload = set_json.call_args.args
        self.assertEqual(key, pending_bubbles_key("user-1"))
        self.assertEqual(payload["user_id"], "user-1")
        self.assertEqual(payload["turn_id"], "turn-1")
        self.assertEqual(payload["batch_id"], "batch-1")
        self.assertEqual(payload["messages"], reply_batch["messages"])
        self.assertEqual(payload["next_send_at"], 1783159200.0)
        self.assertGreaterEqual(set_json.call_args.kwargs["ex"], 30)

    def test_store_reply_timing_state_ignores_empty_user(self):
        with patch("app.core.reply_timing_state.set_json") as set_json:
            stored = store_reply_timing_state(None, {"messages": [{"content": "x"}]})

        self.assertFalse(stored)
        set_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
