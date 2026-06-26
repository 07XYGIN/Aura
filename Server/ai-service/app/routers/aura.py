from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aura_store import AuraNotFoundError, AuraStore, AuraValidationError
from app.db.session import get_db_session
from app.schemas.aura import (
    ChatMessageRequest,
    ConversationFeedbackRequest,
    ConversationSessionRequest,
    MemoryItemRequest,
    RelationshipEventRequest,
    ReportPurchaseRequest,
    UserBehaviorEventRequest,
)
from app.schemas.response import SuccessResponse

router = APIRouter(
    prefix="/api/aura",
    tags=["aura"],
)


def aura_store(session: AsyncSession = Depends(get_db_session)) -> AuraStore:
    return AuraStore(session)


def handle_store_error(error: Exception) -> None:
    if isinstance(error, AuraNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, AuraValidationError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    raise error


@router.post("/sessions", response_model=SuccessResponse)
async def create_session(request: ConversationSessionRequest, store: AuraStore = Depends(aura_store)):
    try:
        return SuccessResponse(data=await store.create_session(request))
    except Exception as error:
        handle_store_error(error)


@router.post("/sessions/{session_id}/messages", response_model=SuccessResponse)
async def add_message(
    session_id: str,
    request: ChatMessageRequest,
    store: AuraStore = Depends(aura_store),
):
    try:
        return SuccessResponse(data=await store.add_message(session_id, request))
    except Exception as error:
        handle_store_error(error)


@router.post("/memories", response_model=SuccessResponse)
async def add_memory_item(request: MemoryItemRequest, store: AuraStore = Depends(aura_store)):
    try:
        return SuccessResponse(data=await store.add_memory_item(request))
    except Exception as error:
        handle_store_error(error)


@router.post("/relationship/events", response_model=SuccessResponse)
async def add_relationship_event(
    request: RelationshipEventRequest,
    store: AuraStore = Depends(aura_store),
):
    try:
        return SuccessResponse(data=await store.add_relationship_event(request))
    except Exception as error:
        handle_store_error(error)


@router.post("/conversation-feedback", response_model=SuccessResponse)
async def submit_conversation_feedback(
    request: ConversationFeedbackRequest,
    store: AuraStore = Depends(aura_store),
):
    try:
        return SuccessResponse(data=await store.add_feedback(request))
    except Exception as error:
        handle_store_error(error)


@router.post("/behavior-events", response_model=SuccessResponse)
async def add_behavior_event(
    request: UserBehaviorEventRequest,
    store: AuraStore = Depends(aura_store),
):
    try:
        return SuccessResponse(data=await store.add_behavior_event(request))
    except Exception as error:
        handle_store_error(error)


@router.get("/emotion-report/preview", response_model=SuccessResponse)
async def get_emotion_report_preview(
    user_id: str = Query(alias="userId"),
    store: AuraStore = Depends(aura_store),
):
    try:
        return SuccessResponse(data=await store.get_emotion_report_preview(user_id))
    except Exception as error:
        handle_store_error(error)


@router.post("/emotion-report/{report_id}/purchase", response_model=SuccessResponse)
async def purchase_emotion_report(
    report_id: str,
    request: ReportPurchaseRequest,
    store: AuraStore = Depends(aura_store),
):
    try:
        return SuccessResponse(data=await store.purchase_emotion_report(request.user_id, report_id))
    except Exception as error:
        handle_store_error(error)
