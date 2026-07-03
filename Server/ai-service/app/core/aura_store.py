from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuraProfile,
    ChatMessage,
    ConversationFeedback,
    ConversationSession,
    EmotionInsightReport,
    EmotionSnapshot,
    MemoryItem,
    RelationshipEvent,
    RelationshipState,
    UserBehaviorEvent,
)
from app.schemas.aura import (
    ChatMessageRequest,
    ConversationFeedbackRequest,
    ConversationSessionRequest,
    MemoryItemRequest,
    RelationshipEventRequest,
    UserBehaviorEventRequest,
)

REPORT_TRIGGER_CHAT_TURNS = 10
REPORT_PRICE_CENTS = 900


class AuraStoreError(Exception):
    pass


class AuraNotFoundError(AuraStoreError):
    pass


class AuraValidationError(AuraStoreError):
    pass


def require_uuid(value: str | UUID | None, field_name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str) or not value.strip():
        raise AuraValidationError(f"{field_name} is required")
    try:
        return UUID(value.strip())
    except ValueError as exc:
        raise AuraValidationError(f"{field_name} must be a valid UUID") from exc


def optional_uuid(value: str | UUID | None, field_name: str) -> UUID | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return require_uuid(value, field_name)


def parse_json_object(value: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if default is None:
        default = {}
    if value is None or value == "":
        return dict(default)
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AuraValidationError("metadata must be valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    return {"value": value}


def parse_json_array(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AuraValidationError("tags must be valid JSON") from exc
        if isinstance(parsed, list):
            return parsed
        return [parsed]
    return [value]


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def now_utc() -> datetime:
    return datetime.now(UTC)


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def datetime_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def decimal_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


class AuraRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_user(self, user_id: UUID) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:user_id))"),
            {"user_id": str(user_id)},
        )

    async def get_latest_aura_profile_id(self, user_id: UUID) -> UUID | None:
        result = await self.session.execute(
            select(AuraProfile.id)
            .where(AuraProfile.user_id == user_id)
            .order_by(AuraProfile.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_relationship_state_id(self, user_id: UUID) -> UUID | None:
        result = await self.session.execute(
            select(RelationshipState.id)
            .where(RelationshipState.user_id == user_id)
            .order_by(RelationshipState.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_session(self, session_id: UUID) -> ConversationSession | None:
        return await self.session.get(ConversationSession, session_id)

    async def get_message(self, message_id: UUID) -> ChatMessage | None:
        return await self.session.get(ChatMessage, message_id)

    async def get_report(self, report_id: UUID) -> EmotionInsightReport | None:
        return await self.session.get(EmotionInsightReport, report_id)

    async def get_latest_report(self, user_id: UUID) -> EmotionInsightReport | None:
        result = await self.session.execute(
            select(EmotionInsightReport)
            .where(EmotionInsightReport.user_id == user_id)
            .order_by(EmotionInsightReport.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_events(self, user_id: UUID, event_type: str) -> int:
        result = await self.session.execute(
            select(func.count(UserBehaviorEvent.id)).where(
                UserBehaviorEvent.user_id == user_id,
                UserBehaviorEvent.event_type == event_type,
            )
        )
        return int(result.scalar_one())

    async def list_recent_emotion_labels(self, user_id: UUID, limit: int = 50) -> list[str]:
        result = await self.session.execute(
            select(EmotionSnapshot.dominant_emotion)
            .where(
                EmotionSnapshot.user_id == user_id,
                EmotionSnapshot.dominant_emotion.is_not(None),
                EmotionSnapshot.dominant_emotion != "",
            )
            .order_by(EmotionSnapshot.created_at.desc())
            .limit(limit)
        )
        return [label for label in result.scalars().all() if label]


class AuraStore:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AuraRepository(session)

    async def create_session(self, request: ConversationSessionRequest) -> dict[str, Any]:
        user_id = require_uuid(request.user_id, "userId")
        requested_session_id = optional_uuid(request.id, "id")

        async with self.session.begin():
            await self.repo.lock_user(user_id)
            if requested_session_id:
                existing = await self.repo.get_session(requested_session_id)
                if existing:
                    if existing.user_id != user_id:
                        raise AuraNotFoundError("session not found")
                    return conversation_session_dict(existing)

            aura_profile_id = optional_uuid(request.aura_profile_id, "auraProfileId")
            if aura_profile_id is None:
                aura_profile_id = await self.repo.get_latest_aura_profile_id(user_id)

            session = ConversationSession(
                id=requested_session_id or uuid4(),
                user_id=user_id,
                aura_profile_id=aura_profile_id,
                channel=clean_text(request.channel) or "chat",
                title=clean_text(request.title),
                status=clean_text(request.status) or "active",
                summary=clean_text(request.summary),
                metadata_json=parse_json_object(request.metadata),
            )
            self.session.add(session)
            await self.session.flush()
            return conversation_session_dict(session)

    async def add_message(self, session_id_value: str, request: ChatMessageRequest) -> dict[str, Any]:
        user_id = require_uuid(request.user_id, "userId")
        session_id = require_uuid(session_id_value, "sessionId")

        async with self.session.begin():
            await self.repo.lock_user(user_id)
            conversation_session = await self.repo.get_session(session_id)
            if conversation_session is None or conversation_session.user_id != user_id:
                raise AuraNotFoundError("session not found")

            message = ChatMessage(
                id=uuid4(),
                session_id=session_id,
                user_id=user_id,
                sender_type=clean_text(request.sender_type) or "assistant",
                sender_id=clean_text(request.sender_id),
                content=clean_text(request.content) or "",
                content_type=clean_text(request.content_type) or "text",
                emotion_label=clean_text(request.emotion_label),
                token_count=request.token_count or 0,
                batch_id=optional_uuid(request.batch_id, "batchId"),
                batch_index=request.batch_index,
                sent_at=request.sent_at,
                metadata_json=parse_json_object(request.metadata),
            )
            if not message.content:
                raise AuraValidationError("content is required")

            self.session.add(message)
            await self.session.flush()

            snapshot = None
            if request.emotion_snapshot:
                snapshot = self._build_emotion_snapshot(
                    user_id=user_id,
                    session_id=session_id,
                    message_id=message.id,
                    request=request.emotion_snapshot,
                )
                self.session.add(snapshot)
                await self.session.flush()

            return {
                "message": chat_message_dict(message),
                "emotionSnapshot": emotion_snapshot_dict(snapshot) if snapshot else None,
            }

    async def add_memory_item(self, request: MemoryItemRequest) -> dict[str, Any]:
        user_id = require_uuid(request.user_id, "userId")

        async with self.session.begin():
            await self.repo.lock_user(user_id)
            memory = MemoryItem(
                id=uuid4(),
                user_id=user_id,
                aura_profile_id=optional_uuid(request.aura_profile_id, "auraProfileId"),
                source_session_id=optional_uuid(request.source_session_id, "sourceSessionId"),
                source_message_id=optional_uuid(request.source_message_id, "sourceMessageId"),
                memory_type=clean_text(request.memory_type) or "chat_signal",
                title=clean_text(request.title),
                content=clean_text(request.content) or "",
                salience=request.salience if request.salience is not None else 50,
                confidence=request.confidence,
                status=clean_text(request.status) or "active",
                tags=parse_json_array(request.tags),
                metadata_json=parse_json_object(request.metadata),
            )
            if not memory.content:
                raise AuraValidationError("content is required")

            self.session.add(memory)
            await self.session.flush()
            return memory_item_dict(memory)

    async def add_relationship_event(self, request: RelationshipEventRequest) -> dict[str, Any]:
        user_id = require_uuid(request.user_id, "userId")

        async with self.session.begin():
            await self.repo.lock_user(user_id)
            relationship_state_id = optional_uuid(request.relationship_state_id, "relationshipStateId")
            if relationship_state_id is None:
                relationship_state_id = await self.repo.get_latest_relationship_state_id(user_id)

            event = RelationshipEvent(
                id=uuid4(),
                user_id=user_id,
                relationship_state_id=relationship_state_id,
                event_type=clean_text(request.event_type) or "chat_turn",
                title=clean_text(request.title),
                description=clean_text(request.description),
                delta_intimacy=request.delta_intimacy or 0,
                delta_trust=request.delta_trust or 0,
                delta_affection=request.delta_affection or 0,
                delta_conflict=request.delta_conflict or 0,
                occurred_at=request.occurred_at or now_utc(),
                metadata_json=parse_json_object(request.metadata),
            )
            self.session.add(event)
            await self.session.flush()
            return relationship_event_dict(event)

    async def add_behavior_event(self, request: UserBehaviorEventRequest) -> dict[str, Any]:
        user_id = require_uuid(request.user_id, "userId")

        async with self.session.begin():
            await self.repo.lock_user(user_id)
            session_id = optional_uuid(request.session_id, "sessionId")
            message_id = optional_uuid(request.message_id, "messageId")
            if session_id:
                conversation_session = await self.repo.get_session(session_id)
                if conversation_session is None or conversation_session.user_id != user_id:
                    raise AuraNotFoundError("session not found")
            if message_id:
                message = await self.repo.get_message(message_id)
                if message is None or message.user_id != user_id:
                    raise AuraNotFoundError("message not found")

            event = UserBehaviorEvent(
                id=uuid4(),
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                event_type=clean_text(request.event_type) or "unknown",
                event_time=request.event_time or now_utc(),
                metadata_json=parse_json_object(request.metadata),
            )
            self.session.add(event)
            await self.session.flush()
            return behavior_event_dict(event)

    async def add_feedback(self, request: ConversationFeedbackRequest) -> dict[str, Any]:
        user_id = require_uuid(request.user_id, "userId")
        session_id = require_uuid(request.session_id, "sessionId")

        async with self.session.begin():
            await self.repo.lock_user(user_id)
            conversation_session = await self.repo.get_session(session_id)
            if conversation_session is None or conversation_session.user_id != user_id:
                raise AuraNotFoundError("session not found")

            feedback = ConversationFeedback(
                id=uuid4(),
                user_id=user_id,
                session_id=session_id,
                score=request.score,
                comment=clean_text(request.comment),
            )
            self.session.add(feedback)

            conversation_session.status = "ended"
            conversation_session.ended_at = now_utc()
            conversation_session.updated_at = now_utc()

            event = UserBehaviorEvent(
                id=uuid4(),
                user_id=user_id,
                session_id=session_id,
                event_type="conversation_feedback",
                event_time=now_utc(),
                metadata_json={"score": request.score},
            )
            self.session.add(event)
            await self.session.flush()
            return feedback_dict(feedback)

    async def get_emotion_report_preview(self, user_id_value: str) -> dict[str, Any]:
        user_id = require_uuid(user_id_value, "userId")

        async with self.session.begin():
            chat_turns = await self.repo.count_events(user_id, "chat_turn")
            response: dict[str, Any] = {
                "eligible": chat_turns >= REPORT_TRIGGER_CHAT_TURNS,
                "chatTurns": chat_turns,
                "roundsRemaining": max(0, REPORT_TRIGGER_CHAT_TURNS - chat_turns),
            }
            if chat_turns < REPORT_TRIGGER_CHAT_TURNS:
                return response

            report = await self.repo.get_latest_report(user_id)
            if report is None:
                report = await self._create_emotion_report(user_id)

            response.update(report_preview_dict(report))
            return response

    async def purchase_emotion_report(self, user_id_value: str, report_id_value: str) -> dict[str, Any]:
        user_id = require_uuid(user_id_value, "userId")
        report_id = require_uuid(report_id_value, "reportId")

        async with self.session.begin():
            await self.repo.lock_user(user_id)
            report = await self.repo.get_report(report_id)
            if report is None or report.user_id != user_id:
                raise AuraNotFoundError("report not found")

            report.status = "paid"
            report.paid_at = now_utc()
            report.updated_at = now_utc()
            await self.session.flush()
            return report_dict(report)

    def _build_emotion_snapshot(
        self,
        user_id: UUID,
        session_id: UUID,
        message_id: UUID,
        request: Any,
    ) -> EmotionSnapshot:
        return EmotionSnapshot(
            id=uuid4(),
            user_id=user_id,
            session_id=optional_uuid(request.session_id, "sessionId") or session_id,
            message_id=optional_uuid(request.message_id, "messageId") or message_id,
            source=clean_text(request.source) or "chat",
            dominant_emotion=clean_text(request.dominant_emotion),
            valence=request.valence,
            arousal=request.arousal,
            intensity=request.intensity,
            emotion_scores=parse_json_object(request.emotion_scores),
            reason=clean_text(request.reason),
        )

    async def _create_emotion_report(self, user_id: UUID) -> EmotionInsightReport:
        labels = await self.repo.list_recent_emotion_labels(user_id, 50)
        keywords = top_emotion_keywords(labels)
        preview_text = f"Aura 注意到，这段时间你反复绕回的感受更像是：{'、'.join(keywords)}。"
        report = EmotionInsightReport(
            id=uuid4(),
            user_id=user_id,
            status="preview",
            price_cents=REPORT_PRICE_CENTS,
            preview_keywords=keywords,
            preview_text=preview_text,
            full_report={
                "weeklyKeywords": keywords,
                "patternAnalysis": [
                    "你这周的情绪不是单点爆发，更像是几类小事慢慢叠在一起。",
                    "当你感到被误解、被催促，或需要很快回应别人时，疲惫感会更明显。",
                ],
                "auraObservation": "Aura 觉得，你不是太敏感，你只是比很多人更早听见了心里的杂音。",
            },
        )
        self.session.add(report)
        await self.session.flush()
        return report


def top_emotion_keywords(labels: list[str]) -> list[str]:
    fallback = ["安静", "疲惫", "想被理解"]
    counts = Counter(to_emotion_keyword(label) for label in labels if label)
    if not counts:
        return fallback

    keywords = [keyword for keyword, _ in counts.most_common(3)]
    for item in fallback:
        if len(keywords) >= 3:
            break
        if item not in keywords:
            keywords.append(item)
    return keywords[:3]


def to_emotion_keyword(label: str | None) -> str:
    if not label:
        return "安静"
    normalized = label.lower()
    if "anxious" in normalized or "焦虑" in normalized:
        return "焦虑"
    if "tired" in normalized or "疲惫" in normalized:
        return "疲惫"
    if "sad" in normalized or "distress" in normalized or "难受" in normalized:
        return "难受"
    if "happy" in normalized or "开心" in normalized:
        return "轻快"
    if "lonely" in normalized or "孤独" in normalized:
        return "孤独"
    return "安静"


def conversation_session_dict(session: ConversationSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "userId": str(session.user_id),
        "auraProfileId": str(session.aura_profile_id) if session.aura_profile_id else None,
        "channel": session.channel,
        "title": session.title,
        "status": session.status,
        "startedAt": datetime_iso(session.started_at),
        "endedAt": datetime_iso(session.ended_at),
        "summary": session.summary,
        "metadata": json_dumps(session.metadata_json),
        "createdAt": datetime_iso(session.created_at),
        "updatedAt": datetime_iso(session.updated_at),
    }


def chat_message_dict(message: ChatMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "sessionId": str(message.session_id),
        "userId": str(message.user_id),
        "senderType": message.sender_type,
        "senderId": message.sender_id,
        "content": message.content,
        "contentType": message.content_type,
        "emotionLabel": message.emotion_label,
        "tokenCount": message.token_count,
        "batchId": str(message.batch_id) if message.batch_id else None,
        "batchIndex": message.batch_index,
        "sentAt": datetime_iso(message.sent_at),
        "metadata": json_dumps(message.metadata_json),
        "createdAt": datetime_iso(message.created_at),
    }


def emotion_snapshot_dict(snapshot: EmotionSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "id": str(snapshot.id),
        "userId": str(snapshot.user_id),
        "sessionId": str(snapshot.session_id) if snapshot.session_id else None,
        "messageId": str(snapshot.message_id) if snapshot.message_id else None,
        "source": snapshot.source,
        "dominantEmotion": snapshot.dominant_emotion,
        "valence": decimal_float(snapshot.valence),
        "arousal": decimal_float(snapshot.arousal),
        "intensity": decimal_float(snapshot.intensity),
        "emotionScores": json_dumps(snapshot.emotion_scores),
        "reason": snapshot.reason,
        "createdAt": datetime_iso(snapshot.created_at),
    }


def memory_item_dict(memory: MemoryItem) -> dict[str, Any]:
    return {
        "id": str(memory.id),
        "userId": str(memory.user_id),
        "auraProfileId": str(memory.aura_profile_id) if memory.aura_profile_id else None,
        "sourceSessionId": str(memory.source_session_id) if memory.source_session_id else None,
        "sourceMessageId": str(memory.source_message_id) if memory.source_message_id else None,
        "memoryType": memory.memory_type,
        "title": memory.title,
        "content": memory.content,
        "salience": memory.salience,
        "confidence": decimal_float(memory.confidence),
        "status": memory.status,
        "tags": json_dumps(memory.tags),
        "metadata": json_dumps(memory.metadata_json),
        "createdAt": datetime_iso(memory.created_at),
        "updatedAt": datetime_iso(memory.updated_at),
    }


def relationship_event_dict(event: RelationshipEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "userId": str(event.user_id),
        "relationshipStateId": str(event.relationship_state_id) if event.relationship_state_id else None,
        "eventType": event.event_type,
        "title": event.title,
        "description": event.description,
        "deltaIntimacy": event.delta_intimacy,
        "deltaTrust": event.delta_trust,
        "deltaAffection": event.delta_affection,
        "deltaConflict": event.delta_conflict,
        "occurredAt": datetime_iso(event.occurred_at),
        "metadata": json_dumps(event.metadata_json),
        "createdAt": datetime_iso(event.created_at),
    }


def feedback_dict(feedback: ConversationFeedback) -> dict[str, Any]:
    return {
        "id": str(feedback.id),
        "userId": str(feedback.user_id),
        "sessionId": str(feedback.session_id),
        "score": feedback.score,
        "comment": feedback.comment,
        "createdAt": datetime_iso(feedback.created_at),
    }


def behavior_event_dict(event: UserBehaviorEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "userId": str(event.user_id),
        "sessionId": str(event.session_id) if event.session_id else None,
        "messageId": str(event.message_id) if event.message_id else None,
        "eventType": event.event_type,
        "eventTime": datetime_iso(event.event_time),
        "metadata": json_dumps(event.metadata_json),
        "createdAt": datetime_iso(event.created_at),
    }


def report_preview_dict(report: EmotionInsightReport) -> dict[str, Any]:
    data = {
        "reportId": str(report.id),
        "status": report.status,
        "priceCents": report.price_cents,
        "previewKeywords": json_dumps(report.preview_keywords),
        "previewText": report.preview_text,
    }
    if report.status == "paid":
        data["fullReport"] = json_dumps(report.full_report)
    return data


def report_dict(report: EmotionInsightReport) -> dict[str, Any]:
    return {
        "id": str(report.id),
        "userId": str(report.user_id),
        "status": report.status,
        "priceCents": report.price_cents,
        "previewKeywords": json_dumps(report.preview_keywords),
        "previewText": report.preview_text,
        "fullReport": json_dumps(report.full_report),
        "paidAt": datetime_iso(report.paid_at),
        "createdAt": datetime_iso(report.created_at),
        "updatedAt": datetime_iso(report.updated_at),
    }
