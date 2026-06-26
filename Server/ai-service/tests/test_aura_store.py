import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.aura_store import parse_json_array, parse_json_object, top_emotion_keywords


class AuraStoreHelperTest(unittest.TestCase):
    def test_top_emotion_keywords_keeps_three_relationship_style_words(self):
        keywords = top_emotion_keywords(["anxious", "tired", "anxious", "lonely"])

        self.assertEqual(keywords, ["焦虑", "疲惫", "孤独"])

    def test_top_emotion_keywords_uses_hsp_fallback_when_no_emotions(self):
        self.assertEqual(top_emotion_keywords([]), ["安静", "疲惫", "想被理解"])

    def test_parse_json_object_accepts_frontend_json_string(self):
        self.assertEqual(
            parse_json_object('{"durationMs":1200,"deepNight":true}'),
            {"durationMs": 1200, "deepNight": True},
        )

    def test_parse_json_array_accepts_frontend_json_string(self):
        self.assertEqual(parse_json_array('["long_term_emotion","plan"]'), ["long_term_emotion", "plan"])


if __name__ == "__main__":
    unittest.main()
