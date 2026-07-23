from __future__ import annotations

import unittest
from uuid import uuid4

from app.core.continuity.knowledge_extractor import (
    build_item_key,
    deterministic_relationship_item_hints,
    normalize_cooldown_days,
    normalize_relationship_chapter_candidate,
    normalize_relationship_item_candidates,
)


class RelationshipKnowledgeExtractorTest(unittest.TestCase):
    """验证关系知识只接受有原文依据、枚举合法且达到门槛的候选。"""

    def valid_item(self, **overrides):
        """构造一条默认可通过白名单和证据校验的共同玩笑候选。"""

        item = {
            "operation": "upsert",
            "item_type": "running_joke",
            "perspective": "shared",
            "world_layer": "shared_history",
            "title": "改太多把自己改懵了",
            "content": "双方会用这句话吐槽项目反复修改。",
            "usage_condition": "项目修改次数很多、而且气氛轻松时偶尔使用。",
            "confidence": 0.9,
            "can_change": True,
            "cooldown_days": 14,
            "phrases": ["改太多把自己改懵了"],
            "evidence": "改太多把自己改懵了",
        }
        item.update(overrides)
        return item

    def valid_chapter(self, **overrides):
        """构造一条刚好高于章节低频门槛的真实共同经历候选。"""

        chapter = {
            "create": True,
            "title": "从关系打分走向共同设计",
            "summary": "小乔和 Aura 决定不用分数衡量关系，改用真实经历保持连续性。",
            "world_layer": "shared_history",
            "importance": 0.8,
            "confidence": 0.75,
            "evidence": "我们决定不再使用关系打分",
        }
        chapter.update(overrides)
        return chapter

    def test_item_evidence_must_come_from_source_or_recent_context(self) -> None:
        """当前原文和真实近期上下文都可作证，模型自行补写的证据必须丢弃。"""

        source_candidate = self.valid_item(evidence="改太多把自己改懵了")
        context_candidate = self.valid_item(
            title="动作描写不要模板化",
            item_type="aura_stance",
            perspective="aura",
            content="Aura 喜欢偶尔使用动作描写，但反对每句话都套模板。",
            evidence="偶尔用一下挺有感觉的",
            phrases=[],
        )
        invented_candidate = self.valid_item(
            title="不存在的共同玩笑",
            evidence="我们一直把发布叫作放烟花",
        )

        source_result = normalize_relationship_item_candidates(
            [source_candidate],
            "是啊，改太多把自己改懵了。",
        )
        context_result = normalize_relationship_item_candidates(
            [context_candidate],
            "把刚才的看法记下来吧。",
            recent_context="Aura：偶尔用一下挺有感觉的，但每句话都写就不是我了。",
        )
        invented_result = normalize_relationship_item_candidates(
            [invented_candidate],
            "今天继续改后端。",
            recent_context="昨天只讨论了关系线程。",
        )

        self.assertEqual(len(source_result), 1)
        self.assertEqual(len(context_result), 1)
        self.assertEqual(invented_result, [])

    def test_unknown_item_enums_are_rejected_instead_of_defaulted(self) -> None:
        """未知类型、视角和事实层不能被静默改成某个合法默认值。"""

        raw = [
            self.valid_item(item_type="relationship_score"),
            self.valid_item(perspective="developer"),
            self.valid_item(world_layer="system_prompt"),
        ]

        result = normalize_relationship_item_candidates(
            raw,
            "改太多把自己改懵了",
        )

        self.assertEqual(result, [])

    def test_low_confidence_item_is_rejected_at_strict_boundary(self) -> None:
        """物件置信度低于 0.6 时丢弃，恰好 0.6 时允许进入服务层。"""

        rejected = normalize_relationship_item_candidates(
            [self.valid_item(confidence=0.599)],
            "改太多把自己改懵了",
        )
        accepted = normalize_relationship_item_candidates(
            [self.valid_item(confidence=0.6)],
            "改太多把自己改懵了",
        )

        self.assertEqual(rejected, [])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["confidence"], 0.6)

    def test_deactivate_requires_valid_target_uuid(self) -> None:
        """停用操作只能指向已存在 UUID，不能靠标题猜测目标。"""

        target_id = str(uuid4())
        result = normalize_relationship_item_candidates(
            [
                {"operation": "deactivate"},
                {"operation": "deactivate", "target_id": "not-a-uuid"},
                {"operation": "deactivate", "targetId": target_id},
            ],
            "不要再用那个称呼了。",
        )

        self.assertEqual(result, [{"operation": "deactivate", "target_id": target_id}])

    def test_supported_world_layers_are_preserved(self) -> None:
        """物件可以属于五种事实层，规范化不能把想象或愿望改写成现实。"""

        for world_layer in ("reality", "shared_history", "imagined", "wish", "promise"):
            with self.subTest(world_layer=world_layer):
                result = normalize_relationship_item_candidates(
                    [self.valid_item(world_layer=world_layer)],
                    "改太多把自己改懵了",
                )
                self.assertEqual(result[0]["world_layer"], world_layer)

    def test_item_key_is_stable_but_scoped_by_type_and_perspective(self) -> None:
        """标题的大小写和空白不影响键，不同语义维度不能发生键复用。"""

        first = build_item_key("nickname", "user", " Baby Qiao ")
        normalized = build_item_key("nickname", "user", "babyqiao")
        other_type = build_item_key("codeword", "user", "babyqiao")
        other_perspective = build_item_key("nickname", "shared", "babyqiao")

        self.assertEqual(first, normalized)
        self.assertNotEqual(first, other_type)
        self.assertNotEqual(first, other_perspective)
        self.assertTrue(first.startswith("knowledge:nickname:"))
        self.assertNotIn("baby", first)

    def test_private_phrases_require_evidence_are_deduplicated_and_bounded(self) -> None:
        """私人短语只保留真实出现项，按大小写去重，并最多保存五条。"""

        source = "宝宝贴贴，过来，少装模作样，一会儿见，先别急，慢慢来。"
        candidate = self.valid_item(
            item_type="codeword",
            title="私人短语",
            evidence="宝宝贴贴",
            phrases=[
                "宝宝贴贴",
                "过来",
                "少装模作样",
                "一会儿见",
                "先别急",
                "慢慢来",
                "宝宝贴贴",
                "从未说过的暗号",
            ],
        )

        result = normalize_relationship_item_candidates([candidate], source)

        self.assertEqual(
            result[0]["phrases"],
            ["宝宝贴贴", "过来", "少装模作样", "一会儿见", "先别急"],
        )

    def test_private_phrase_can_use_recent_context_as_evidence(self) -> None:
        """短语可以来自真实近期对话，但不能来自候选 content 自身。"""

        candidate = self.valid_item(
            item_type="nickname",
            title="宝宝",
            evidence="以后叫我宝宝",
            phrases=["宝宝", "模型自创昵称"],
        )
        result = normalize_relationship_item_candidates(
            [candidate],
            "好，记下来。",
            recent_context="小乔：以后叫我宝宝，但别每句话都叫。",
        )

        self.assertEqual(result[0]["phrases"], ["宝宝"])

    def test_cooldown_defaults_and_numeric_boundaries(self) -> None:
        """私人语言默认冷却 14 天，普通知识默认 0 天，并限制在 0 到 3650。"""

        self.assertEqual(normalize_cooldown_days(None, "nickname"), 14)
        self.assertEqual(normalize_cooldown_days("invalid", "aura_stance"), 0)
        self.assertEqual(normalize_cooldown_days(-1, "running_joke"), 0)
        self.assertEqual(normalize_cooldown_days(3651, "codeword"), 3650)
        self.assertEqual(normalize_cooldown_days("30", "ritual"), 30)

    def test_chapter_accepts_only_at_low_frequency_thresholds(self) -> None:
        """章节重要度至少 0.8、置信度至少 0.75，边界值本身有效。"""

        source = "我们决定不再使用关系打分"
        accepted = normalize_relationship_chapter_candidate(self.valid_chapter(), source)
        low_importance = normalize_relationship_chapter_candidate(
            self.valid_chapter(importance=0.799),
            source,
        )
        low_confidence = normalize_relationship_chapter_candidate(
            self.valid_chapter(confidence=0.749),
            source,
        )
        not_requested = normalize_relationship_chapter_candidate(
            self.valid_chapter(create=False),
            source,
        )

        self.assertIsNotNone(accepted)
        self.assertEqual(accepted["importance"], 0.8)
        self.assertEqual(accepted["confidence"], 0.75)
        self.assertIsNone(low_importance)
        self.assertIsNone(low_confidence)
        self.assertIsNone(not_requested)

    def test_chapter_accepts_recent_evidence_but_rejects_invented_evidence(self) -> None:
        """章节与物件一样只能引用当前或近期真实对话证据。"""

        chapter = self.valid_chapter()
        from_context = normalize_relationship_chapter_candidate(
            chapter,
            "我也觉得这是个阶段变化。",
            recent_context="小乔：我们决定不再使用关系打分。",
        )
        invented = normalize_relationship_chapter_candidate(
            chapter,
            "今天只是普通聊天。",
            recent_context="昨天讨论了天气。",
        )

        self.assertIsNotNone(from_context)
        self.assertIsNone(invented)

    def test_chapter_rejects_imagined_world_even_with_max_scores(self) -> None:
        """共同想象不能因为高分被错误升级为真实关系章节。"""

        source = "假如我们一起去旅行"
        result = normalize_relationship_chapter_candidate(
            self.valid_chapter(
                title="一起旅行",
                summary="双方想象一起去旅行。",
                world_layer="imagined",
                importance=1,
                confidence=1,
                evidence=source,
            ),
            source,
        )

        self.assertIsNone(result)

    def test_deterministic_rules_capture_explicit_style_and_nickname_feedback(self) -> None:
        """高置信度客服、机械安慰和昵称指令应生成对应关系知识。"""

        service_style = deterministic_relationship_item_hints("你这句话太客服了")
        comfort_boundary = deterministic_relationship_item_hints("别每次都安慰我，先正常接话")
        nickname = deterministic_relationship_item_hints("以后叫我宝宝")

        self.assertEqual(service_style[0]["item_type"], "action_style")
        self.assertEqual(service_style[0]["title"], "避免客服式表达")
        self.assertEqual(comfort_boundary[0]["item_type"], "boundary")
        self.assertEqual(comfort_boundary[0]["title"], "不要机械安慰")
        self.assertEqual(nickname[0]["item_type"], "nickname")
        self.assertEqual(nickname[0]["title"], "宝宝")
        self.assertEqual(nickname[0]["phrases"], ["宝宝"])
        self.assertEqual(nickname[0]["cooldown_days"], 3)

    def test_negated_customer_service_feedback_is_not_misclassified(self) -> None:
        """否认说过“太客服”时不能反向建立说话风格规则。"""

        self.assertEqual(
            deterministic_relationship_item_hints("我没说你太客服，我说的是旧版文案"),
            [],
        )

    def test_quoted_comfort_example_is_not_misclassified_as_boundary(self) -> None:
        """用户说明自己只是在举例时，不应把引号里的命令当真实边界。"""

        self.assertEqual(
            deterministic_relationship_item_hints("我不是说“不要每次都安慰”，只是在举例"),
            [],
        )

    def test_negated_nickname_instruction_is_not_misclassified(self) -> None:
        """“没说以后叫我”不能被正则截取成肯定昵称约定。"""

        self.assertEqual(
            deterministic_relationship_item_hints("我没说以后叫我宝宝"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
