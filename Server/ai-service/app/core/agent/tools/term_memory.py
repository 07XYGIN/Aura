import logging
import os
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector

from app.core.config import SYNC_DATABASE_URL
from app.core.agent.memory_judge import judge_memory_dedup

MemoryScope = Literal["long", "mid", "all"]


def read_float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(0.0, min(1.0, value))


def read_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(0, value)


LONG_TERM_COLLECTION_NAME = "aura"
MEDIUM_TERM_COLLECTION_NAME = "aura_mid_term"
MEMORY_COLLECTION_NAME = LONG_TERM_COLLECTION_NAME
MEDIUM_MEMORY_FORGET_DAYS = 5
MEMORY_RELEVANCE_THRESHOLD = read_float_env("MEMORY_RELEVANCE_THRESHOLD", 0.55)
LONG_MEMORY_RECALL_COOLDOWN_MINUTES = read_int_env("LONG_MEMORY_RECALL_COOLDOWN_MINUTES", 180)
LONG_MEMORY_COOLDOWN_BYPASS_THRESHOLD = read_float_env("LONG_MEMORY_COOLDOWN_BYPASS_THRESHOLD", 0.78)
LONG_MEMORY_COOLDOWN_PENALTY = read_float_env("LONG_MEMORY_COOLDOWN_PENALTY", 0.25)
LONG_MEMORY_DEDUP_THRESHOLD = read_float_env("LONG_MEMORY_DEDUP_THRESHOLD", 0.75)
LONG_MEMORY_DEDUP_CANDIDATES = read_int_env("LONG_MEMORY_DEDUP_CANDIDATES", 3)
MID_MEMORY_PROMOTION_RECALL_THRESHOLD = read_int_env("MID_MEMORY_PROMOTION_RECALL_THRESHOLD", 3)
EXPLICIT_MEMORY_LOOKUP_KEYWORDS = (
    "记忆",
    "记得我",
    "你记得",
    "偏好",
    "习惯",
    "个人信息",
    "资料",
)
MEMORY_CATALOG_LOOKUP_KEYWORDS = (
    "所有记忆",
    "全部记忆",
    "完整记忆",
    "长期记忆",
    "中期记忆",
    "记得我什么",
    "你记得我什么",
)

embeddings = OllamaEmbeddings(
    model="nomic-embed-text:latest"
)


def get_memory_vector_store(collection_name: str = LONG_TERM_COLLECTION_NAME) -> PGVector:
    return PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=SYNC_DATABASE_URL,
        use_jsonb=True,
    )


def save_memory(
    user_id: str,
    content: str,
    title: str,
    create_time: str,
    memory_scope: Literal["long", "mid"] = "long",
    confidence: float | None = None,
    signals: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> str | None:
    content = (content or "").strip()
    if not content:
        return None

    scope = "mid" if memory_scope == "mid" else "long"
    metadata = build_memory_metadata(
        user_id=user_id,
        title=title,
        create_time=create_time,
        memory_scope=scope,
    )
    if confidence is not None:
        metadata["confidence"] = confidence
    if signals:
        metadata["signals"] = signals
    if extra_metadata:
        metadata.update({key: value for key, value in extra_metadata.items() if value is not None})

    if scope == "long":
        return save_long_memory(user_id=user_id, content=content, metadata=metadata)

    store = get_memory_vector_store(collection_name_for_scope(scope))
    store.add_documents([Document(page_content=content, metadata=metadata)])
    return str(metadata["memory_key"])


def build_memory_metadata(
    user_id: str,
    title: str,
    create_time: str,
    memory_scope: Literal["long", "mid"],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "user_id": user_id,
        "title": title,
        "create_time": create_time,
        "memory_scope": memory_scope,
        "memory_key": str(uuid4()),
        "status": "active",
    }
    if memory_scope == "long":
        metadata["last_recalled_at"] = None
    if memory_scope == "mid":
        metadata["last_recalled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        metadata["forget_after_days"] = MEDIUM_MEMORY_FORGET_DAYS
        metadata["recall_count"] = 0
    return metadata


def save_long_memory(user_id: str, content: str, metadata: dict[str, Any]) -> str | None:
    store = get_memory_vector_store(LONG_TERM_COLLECTION_NAME)
    similar = find_similar_long_memory(user_id=user_id, content=content, store=store)
    if similar is None:
        store.add_documents([Document(page_content=content, metadata=metadata)])
        return str(metadata["memory_key"])

    existing_doc, score = similar
    existing_key = existing_doc.metadata.get("memory_key")
    if not isinstance(existing_key, str) or not existing_key:
        store.add_documents([Document(page_content=content, metadata=metadata)])
        return str(metadata["memory_key"])

    decision = judge_memory_dedup(
        new_content=content,
        existing_content=existing_doc.page_content,
        existing_metadata=existing_doc.metadata,
    )
    metadata["dedup_similarity_score"] = round(score, 4)
    metadata["dedup_decision"] = decision["decision"]
    metadata["dedup_confidence"] = decision["confidence"]

    if decision["decision"] == "duplicate":
        touch_memory_keys(
            user_id=user_id,
            memory_keys=[existing_key],
            collection_name=LONG_TERM_COLLECTION_NAME,
        )
        return existing_key

    if decision["decision"] == "update":
        metadata["supersedes"] = existing_key
        metadata["supersede_reason"] = decision["reason"]
        store.add_documents([Document(page_content=content, metadata=metadata)])
        mark_memory_superseded(
            user_id=user_id,
            memory_key=existing_key,
            superseded_by=str(metadata["memory_key"]),
            reason=decision["reason"],
        )
        return str(metadata["memory_key"])

    store.add_documents([Document(page_content=content, metadata=metadata)])
    return str(metadata["memory_key"])


def find_similar_long_memory(
    user_id: str,
    content: str,
    store: PGVector | None = None,
) -> tuple[Document, float] | None:
    store = store or get_memory_vector_store(LONG_TERM_COLLECTION_NAME)
    candidate_count = max(LONG_MEMORY_DEDUP_CANDIDATES, 1)
    try:
        results = store.similarity_search_with_relevance_scores(
            content,
            k=candidate_count,
            filter={"user_id": user_id},
            score_threshold=LONG_MEMORY_DEDUP_THRESHOLD,
        )
    except Exception:
        logging.exception("Failed to search similar long memories for dedup")
        return None

    for doc, score in sorted(results, key=lambda item: item[1], reverse=True):
        relevance_score = max(0.0, min(1.0, float(score)))
        if relevance_score < LONG_MEMORY_DEDUP_THRESHOLD:
            continue

        metadata = dict(doc.metadata or {})
        if not is_memory_retrievable(metadata, "long"):
            continue

        return Document(page_content=doc.page_content, metadata=metadata), relevance_score
    return None


def search_memory(user_id: str, query: str, k: int = 5, memory_scope: MemoryScope = "all") -> list[Document]:
    layered = search_layered_memories(user_id=user_id, query=query, k=k)
    if memory_scope == "long":
        return layered["long"][:k]
    if memory_scope == "mid":
        return layered["mid"][:k]
    return (layered["long"] + layered["mid"])[:k]


def search_layered_memories(user_id: str, query: str, k: int = 5) -> dict[str, list[Document]]:
    long_docs = search_memory_collection(
        user_id=user_id,
        query=query,
        k=k,
        collection_name=LONG_TERM_COLLECTION_NAME,
        memory_scope="long",
    )
    mid_docs = search_memory_collection(
        user_id=user_id,
        query=query,
        k=k,
        collection_name=MEDIUM_TERM_COLLECTION_NAME,
        memory_scope="mid",
    )
    touch_recalled_memories(user_id, long_docs, LONG_TERM_COLLECTION_NAME)
    touch_recalled_memories(user_id, mid_docs, MEDIUM_TERM_COLLECTION_NAME)
    return {
        "long": long_docs,
        "mid": mid_docs,
    }


def search_memory_collection(
    user_id: str,
    query: str,
    k: int,
    collection_name: str,
    memory_scope: Literal["long", "mid"],
) -> list[Document]:
    if is_memory_catalog_lookup(query):
        return list_memory_documents(user_id, collection_name, memory_scope, k)

    store = get_memory_vector_store(collection_name)
    candidate_count = max(k * 5, k)
    try:
        results = store.similarity_search_with_relevance_scores(
            query,
            k=candidate_count,
            filter={"user_id": user_id},
            score_threshold=MEMORY_RELEVANCE_THRESHOLD,
        )
    except Exception:
        logging.exception(
            "Failed to search %s memory collection user_id=%s query=%s",
            memory_scope,
            user_id,
            query,
        )
        return []

    return rank_memory_results(
        results,
        memory_scope,
        bypass_long_cooldown=is_explicit_memory_lookup(query),
    )[:k]


def list_memory_documents(
    user_id: str,
    collection_name: str,
    memory_scope: Literal["long", "mid"],
    k: int,
) -> list[Document]:
    docs: list[Document] = []
    for row in fetch_memory_rows(user_id, collection_name):
        metadata = dict(row["cmetadata"] or {})
        if not is_memory_retrievable(metadata, memory_scope):
            continue
        metadata.setdefault("content", row["document"])
        metadata.setdefault("memory_scope", memory_scope)
        metadata.setdefault("status", "active")
        docs.append(Document(page_content=row["document"], metadata=metadata))

    docs.sort(key=lambda doc: memory_sort_key(doc.metadata), reverse=True)
    return docs[:k]


def format_memory_context(user_id: str, query: str, k: int = 5) -> str:
    layered = search_layered_memories(user_id=user_id, query=query, k=k)
    sections: list[str] = []
    if layered["long"]:
        sections.append("长期记忆（稳定事实，仅在当前话题确实相关时自然引用）：\n" + format_docs(layered["long"]))
    if layered["mid"]:
        sections.append("中期记忆（近期线索，3-5 天未提及会淡出）：\n" + format_docs(layered["mid"]))
    if not sections:
        return "没有检索到可引用的长期或中期记忆。不要编造用户偏好、天气、城市、食物或共同经历。"
    return "\n\n".join(sections)


def format_docs(docs: list[Document]) -> str:
    lines: list[str] = []
    for doc in docs:
        title = doc.metadata.get("title") or "未命名记忆"
        create_time = doc.metadata.get("create_time") or "未知时间"
        confidence = doc.metadata.get("confidence")
        confidence_text = f"，置信度 {confidence}" if confidence is not None else ""
        lines.append(f"- {title}（{create_time}{confidence_text}）：{doc.page_content}")
    return "\n".join(lines)


def list_memories_by_user(
    user_id: str,
    page: int = 1,
    page_size: int = 10,
    memory_scope: MemoryScope = "long",
    include_inactive: bool = False,
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size
    scopes: list[Literal["long", "mid"]]
    if memory_scope == "mid":
        scopes = ["mid"]
    elif memory_scope == "all":
        scopes = ["long", "mid"]
    else:
        scopes = ["long"]

    items: list[dict[str, Any]] = []
    for scope in scopes:
        rows = fetch_memory_rows(user_id, collection_name_for_scope(scope))
        for row in rows:
            metadata = dict(row["cmetadata"] or {})
            is_retrievable = is_memory_retrievable(metadata, scope)
            if not include_inactive and not is_retrievable:
                continue
            metadata.setdefault("content", row["document"])
            metadata.setdefault("memory_scope", scope)
            metadata.setdefault("status", "active")
            items.append(
                {
                    "id": str(row["id"]),
                    "memory_key": metadata.get("memory_key"),
                    "status": metadata.get("status"),
                    "supersedes": metadata.get("supersedes"),
                    "superseded_by": metadata.get("superseded_by"),
                    "promoted_to_long": metadata.get("promoted_to_long"),
                    "promoted_memory_key": metadata.get("promoted_memory_key"),
                    "is_retrievable": is_retrievable,
                    "metadata": metadata,
                    "page_content": row["document"],
                    "type": "Document",
                }
            )

    items.sort(key=lambda item: memory_sort_key(item["metadata"]), reverse=True)
    total = len(items)
    page_items = items[offset:offset + page_size]

    return {
        "items": page_items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": offset + len(page_items) < total,
    }


def fetch_memory_rows(user_id: str, collection_name: str) -> list[dict[str, Any]]:
    with psycopg.connect(SYNC_DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.id, e.document, e.cmetadata
                FROM langchain_pg_embedding e
                JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                WHERE c.name = %(collection_name)s
                  AND e.cmetadata ->> 'user_id' = %(user_id)s
                ORDER BY e.cmetadata ->> 'create_time' DESC NULLS LAST, e.id DESC
                """,
                {
                    "collection_name": collection_name,
                    "user_id": user_id,
                },
            )
            return list(cursor.fetchall())


def get_memory_retention_status(user_id: str) -> dict[str, Any]:
    return {
        "plan": "permanent",
        "permanent": True,
        "daysRemaining": None,
        "shouldPrompt": False,
        "paywall": False,
        "longTerm": {
            "permanent": True,
            "vectorIndexed": True,
        },
        "midTerm": {
            "forgetAfterDays": MEDIUM_MEMORY_FORGET_DAYS,
            "promotionRecallThreshold": MID_MEMORY_PROMOTION_RECALL_THRESHOLD,
            "policy": "not_recalled_within_window",
        },
        "shortTerm": {
            "source": "chat_history",
        },
    }


def delete_memory_by_id(user_id: str, memory_id: str) -> bool:
    normalized_memory_id = memory_id.strip()
    if not normalized_memory_id:
        return False

    deleted_count = 0
    with psycopg.connect(SYNC_DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            for collection_name in (LONG_TERM_COLLECTION_NAME, MEDIUM_TERM_COLLECTION_NAME):
                cursor.execute(
                    """
                    DELETE FROM langchain_pg_embedding e
                    USING langchain_pg_collection c
                    WHERE e.collection_id = c.uuid
                      AND c.name = %(collection_name)s
                      AND e.cmetadata ->> 'user_id' = %(user_id)s
                      AND e.id = %(memory_id)s
                    """,
                    {
                        "collection_name": collection_name,
                        "user_id": user_id,
                        "memory_id": normalized_memory_id,
                    },
                )
                deleted_count += cursor.rowcount
        conn.commit()

    return deleted_count > 0


def clear_memories_by_user(user_id: str, memory_scope: MemoryScope = "all") -> int:
    collections = (
        [collection_name_for_scope(memory_scope)]
        if memory_scope in {"long", "mid"}
        else [LONG_TERM_COLLECTION_NAME, MEDIUM_TERM_COLLECTION_NAME]
    )
    deleted_count = 0
    with psycopg.connect(SYNC_DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            for collection_name in collections:
                cursor.execute(
                    """
                    DELETE FROM langchain_pg_embedding e
                    USING langchain_pg_collection c
                    WHERE e.collection_id = c.uuid
                      AND c.name = %(collection_name)s
                      AND e.cmetadata ->> 'user_id' = %(user_id)s
                    """,
                    {
                        "collection_name": collection_name,
                        "user_id": user_id,
                    },
                )
                deleted_count += cursor.rowcount
        conn.commit()

    return deleted_count


def is_memory_retrievable(metadata: dict[str, Any], memory_scope: Literal["long", "mid"]) -> bool:
    if metadata.get("status") == "superseded":
        return False

    if memory_scope == "mid" and metadata.get("promoted_to_long") is True:
        return False

    if memory_scope == "long":
        return True

    reference_time = (
        parse_memory_create_time(metadata.get("last_recalled_at"))
        or parse_memory_create_time(metadata.get("create_time"))
    )
    if reference_time is None:
        return True

    forget_after_days = metadata.get("forget_after_days")
    if not isinstance(forget_after_days, int):
        forget_after_days = MEDIUM_MEMORY_FORGET_DAYS
    return datetime.now() - reference_time < timedelta(days=forget_after_days)


def rank_memory_results(
    results: list[tuple[Document, float]],
    memory_scope: Literal["long", "mid"],
    now: datetime | None = None,
    bypass_long_cooldown: bool = False,
) -> list[Document]:
    now = now or datetime.now()
    ranked: list[tuple[Document, float]] = []
    for doc, score in results:
        metadata = dict(doc.metadata or {})
        if not is_memory_retrievable(metadata, memory_scope):
            continue

        relevance_score = max(0.0, min(1.0, float(score)))
        adjusted_score = relevance_score
        if (
            memory_scope == "long"
            and not bypass_long_cooldown
            and is_long_memory_in_cooldown(metadata, now)
            and relevance_score < LONG_MEMORY_COOLDOWN_BYPASS_THRESHOLD
        ):
            metadata["recently_recalled"] = True
            adjusted_score = max(0.0, relevance_score - LONG_MEMORY_COOLDOWN_PENALTY)

        if adjusted_score < MEMORY_RELEVANCE_THRESHOLD:
            continue

        metadata["relevance_score"] = round(relevance_score, 4)
        metadata["adjusted_relevance_score"] = round(adjusted_score, 4)
        ranked.append((Document(page_content=doc.page_content, metadata=metadata), adjusted_score))

    ranked.sort(key=lambda item: item[1], reverse=True)
    return [doc for doc, _ in ranked]


def is_explicit_memory_lookup(query: str) -> bool:
    normalized = (query or "").strip().lower()
    return any(keyword in normalized for keyword in EXPLICIT_MEMORY_LOOKUP_KEYWORDS)


def is_memory_catalog_lookup(query: str) -> bool:
    normalized = (query or "").strip().lower()
    return any(keyword in normalized for keyword in MEMORY_CATALOG_LOOKUP_KEYWORDS)


def is_long_memory_in_cooldown(metadata: dict[str, Any], now: datetime | None = None) -> bool:
    last_recalled_at = parse_memory_create_time(metadata.get("last_recalled_at"))
    if last_recalled_at is None:
        return False

    now = now or datetime.now()
    return now - last_recalled_at < timedelta(minutes=LONG_MEMORY_RECALL_COOLDOWN_MINUTES)


def touch_recalled_memories(user_id: str, docs: list[Document], collection_name: str) -> None:
    memory_keys = [
        doc.metadata.get("memory_key")
        for doc in docs
        if isinstance(doc.metadata.get("memory_key"), str)
    ]
    if not memory_keys:
        return

    touch_memory_keys(user_id=user_id, memory_keys=memory_keys, collection_name=collection_name)
    if collection_name == MEDIUM_TERM_COLLECTION_NAME:
        promote_mid_term_memories(user_id=user_id, memory_keys=memory_keys)


def touch_memory_keys(user_id: str, memory_keys: list[str], collection_name: str) -> None:
    if not memory_keys:
        return

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
    if collection_name == MEDIUM_TERM_COLLECTION_NAME:
        metadata_update_sql = """
                    COALESCE(e.cmetadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'last_recalled_at', %(now_text)s::text,
                        'recall_count',
                        CASE
                            WHEN e.cmetadata ->> 'recall_count' ~ '^[0-9]+$'
                            THEN (e.cmetadata ->> 'recall_count')::int + 1
                            ELSE 1
                        END
                    )
        """
    else:
        metadata_update_sql = """
                    COALESCE(e.cmetadata, '{}'::jsonb) ||
                    jsonb_build_object('last_recalled_at', %(now_text)s::text)
        """

    try:
        with psycopg.connect(SYNC_DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE langchain_pg_embedding e
                    SET cmetadata = {metadata_update_sql}
                    FROM langchain_pg_collection c
                    WHERE e.collection_id = c.uuid
                      AND c.name = %(collection_name)s
                      AND e.cmetadata ->> 'user_id' = %(user_id)s
                      AND e.cmetadata ->> 'memory_key' = ANY(%(memory_keys)s)
                      AND COALESCE(e.cmetadata ->> 'status', 'active') <> 'superseded'
                    """,
                    {
                        "collection_name": collection_name,
                        "user_id": user_id,
                        "memory_keys": memory_keys,
                        "now_text": now_text,
                    },
                )
            conn.commit()
    except Exception:
        return


def touch_mid_term_memories(user_id: str, docs: list[Document]) -> None:
    touch_recalled_memories(user_id, docs, MEDIUM_TERM_COLLECTION_NAME)


def mark_memory_superseded(user_id: str, memory_key: str, superseded_by: str, reason: str) -> None:
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with psycopg.connect(SYNC_DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE langchain_pg_embedding e
                    SET cmetadata = COALESCE(e.cmetadata, '{}'::jsonb) ||
                        jsonb_build_object(
                            'status', 'superseded',
                            'superseded_at', %(now_text)s::text,
                            'superseded_by', %(superseded_by)s::text,
                            'supersede_reason', %(reason)s::text
                        )
                    FROM langchain_pg_collection c
                    WHERE e.collection_id = c.uuid
                      AND c.name = %(collection_name)s
                      AND e.cmetadata ->> 'user_id' = %(user_id)s
                      AND e.cmetadata ->> 'memory_key' = %(memory_key)s
                    """,
                    {
                        "collection_name": LONG_TERM_COLLECTION_NAME,
                        "user_id": user_id,
                        "memory_key": memory_key,
                        "superseded_by": superseded_by,
                        "reason": reason[:160],
                        "now_text": now_text,
                    },
                )
            conn.commit()
    except Exception:
        logging.exception("Failed to mark long memory superseded user_id=%s memory_key=%s", user_id, memory_key)


def promote_mid_term_memories(user_id: str, memory_keys: list[str]) -> None:
    if not memory_keys or MID_MEMORY_PROMOTION_RECALL_THRESHOLD <= 0:
        return

    rows = fetch_promotable_mid_memory_rows(user_id=user_id, memory_keys=memory_keys)
    for row in rows:
        metadata = dict(row["cmetadata"] or {})
        if not is_memory_retrievable(metadata, "mid"):
            continue

        mid_key = metadata.get("memory_key")
        if not isinstance(mid_key, str) or not mid_key:
            continue

        promoted_key = save_memory(
            user_id=user_id,
            content=row["document"],
            title=str(metadata.get("title") or "Recent context"),
            create_time=str(metadata.get("create_time") or datetime.now().strftime("%Y-%m-%d %H:%M")),
            memory_scope="long",
            confidence=metadata.get("confidence") if isinstance(metadata.get("confidence"), (float, int)) else None,
            signals=metadata.get("signals") if isinstance(metadata.get("signals"), list) else None,
            extra_metadata={
                "promoted_from_mid_key": mid_key,
                "promoted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
        )
        if promoted_key:
            mark_mid_memory_promoted(user_id=user_id, memory_key=mid_key, promoted_memory_key=promoted_key)


def fetch_promotable_mid_memory_rows(user_id: str, memory_keys: list[str]) -> list[dict[str, Any]]:
    try:
        with psycopg.connect(SYNC_DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT e.id, e.document, e.cmetadata
                    FROM langchain_pg_embedding e
                    JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                    WHERE c.name = %(collection_name)s
                      AND e.cmetadata ->> 'user_id' = %(user_id)s
                      AND e.cmetadata ->> 'memory_key' = ANY(%(memory_keys)s)
                      AND COALESCE(e.cmetadata ->> 'status', 'active') <> 'superseded'
                      AND COALESCE(e.cmetadata ->> 'promoted_to_long', 'false') <> 'true'
                      AND CASE
                            WHEN e.cmetadata ->> 'recall_count' ~ '^[0-9]+$'
                            THEN (e.cmetadata ->> 'recall_count')::int
                            ELSE 0
                          END >= %(promotion_threshold)s
                    """,
                    {
                        "collection_name": MEDIUM_TERM_COLLECTION_NAME,
                        "user_id": user_id,
                        "memory_keys": memory_keys,
                        "promotion_threshold": MID_MEMORY_PROMOTION_RECALL_THRESHOLD,
                    },
                )
                return list(cursor.fetchall())
    except Exception:
        logging.exception("Failed to fetch promotable mid-term memories user_id=%s", user_id)
        return []


def mark_mid_memory_promoted(user_id: str, memory_key: str, promoted_memory_key: str) -> None:
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with psycopg.connect(SYNC_DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE langchain_pg_embedding e
                    SET cmetadata = COALESCE(e.cmetadata, '{}'::jsonb) ||
                        jsonb_build_object(
                            'promoted_to_long', true,
                            'promoted_at', %(now_text)s::text,
                            'promoted_memory_key', %(promoted_memory_key)s::text
                        )
                    FROM langchain_pg_collection c
                    WHERE e.collection_id = c.uuid
                      AND c.name = %(collection_name)s
                      AND e.cmetadata ->> 'user_id' = %(user_id)s
                      AND e.cmetadata ->> 'memory_key' = %(memory_key)s
                    """,
                    {
                        "collection_name": MEDIUM_TERM_COLLECTION_NAME,
                        "user_id": user_id,
                        "memory_key": memory_key,
                        "promoted_memory_key": promoted_memory_key,
                        "now_text": now_text,
                    },
                )
            conn.commit()
    except Exception:
        logging.exception("Failed to mark mid-term memory promoted user_id=%s memory_key=%s", user_id, memory_key)


def parse_memory_create_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    for fmt, width in (
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%d", 10),
    ):
        try:
            return datetime.strptime(value.strip()[:width], fmt)
        except ValueError:
            continue

    return None


def memory_sort_key(metadata: dict[str, Any]) -> datetime:
    return (
        parse_memory_create_time(metadata.get("last_recalled_at"))
        or parse_memory_create_time(metadata.get("create_time"))
        or datetime.min
    )


def collection_name_for_scope(memory_scope: MemoryScope | Literal["long", "mid"]) -> str:
    return MEDIUM_TERM_COLLECTION_NAME if memory_scope == "mid" else LONG_TERM_COLLECTION_NAME


def has_permanent_memory(user_id: str) -> bool:
    try:
        with psycopg.connect(SYNC_DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT permanent_memory
                    FROM user_memory_entitlement
                    WHERE user_id = CAST(%(user_id)s AS uuid)
                      AND (expires_at IS NULL OR expires_at > now())
                    """,
                    {
                        "user_id": user_id,
                    },
                )
                row = cursor.fetchone()
                return bool(row and row["permanent_memory"])
    except Exception:
        return False
