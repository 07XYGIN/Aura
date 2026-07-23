"""Aura 分层向量记忆的保存、检索、整理、遗忘和晋升逻辑。"""

import logging
import os
import math
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector

from app.core.config import SYNC_DATABASE_URL
from app.core.agent.judges.memory import judge_memory_dedup, merge_memory_contents
from app.db.models import LangchainPgCollection, LangchainPgEmbedding
from app.db.session import SyncSessionLocal

MemoryScope = Literal["long", "mid", "all"]


def read_float_env(name: str, default: float) -> float:
    """读取 0 到 1 的浮点环境变量；无效值使用默认值。"""

    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(0.0, min(1.0, value))


def read_int_env(name: str, default: int) -> int:
    """读取非负整数环境变量；无效值使用默认值。"""

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
LONG_MEMORY_MERGE_THRESHOLD = read_float_env("LONG_MEMORY_MERGE_THRESHOLD", 0.85)
LONG_MEMORY_MERGE_SCAN_LIMIT = read_int_env("LONG_MEMORY_MERGE_SCAN_LIMIT", 300)
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
    """创建指定 collection 的 PGVector 访问对象。"""

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
    skip_dedup: bool = False,
) -> str | None:
    """保存一条长期或中期记忆。

    Args:
        user_id: 记忆所属用户。
        content: 需要被未来检索的事实性正文。
        title: 用于列表展示的短标题。
        create_time: 业务创建时间文本。
        memory_scope: ``long`` 永久保存，``mid`` 按遗忘策略管理。
        confidence: 可选的 judge 置信度。
        signals: 触发写入的可解释信号。
        extra_metadata: 需要和标准 metadata 合并的附加字段。
        skip_dedup: 是否跳过长期记忆相似度和 LLM 去重。

    Returns:
        保存成功返回 memory key；内容为空或判定为重复时返回 ``None``。
    """

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

    if scope == "long" and not skip_dedup:
        return save_long_memory(user_id=user_id, content=content, metadata=metadata)
    if scope == "long":
        store = get_memory_vector_store(LONG_TERM_COLLECTION_NAME)
        store.add_documents([Document(page_content=content, metadata=metadata)])
        return str(metadata["memory_key"])

    store = get_memory_vector_store(collection_name_for_scope(scope))
    store.add_documents([Document(page_content=content, metadata=metadata)])
    return str(metadata["memory_key"])


def build_memory_metadata(
    user_id: str,
    title: str,
    create_time: str,
    memory_scope: Literal["long", "mid"],
) -> dict[str, Any]:
    """构造向量文档公共 metadata，并补充不同层级的生命周期字段。"""

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
    """对长期记忆执行相似检索和去重判断后写入 PGVector。"""

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
    """查找最接近的新长期记忆候选，并返回文档与相关度。"""

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
        logging.exception("检索相似长期记忆失败")
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


def list_memory_merge_candidates(
    user_id: str,
    threshold: float = LONG_MEMORY_MERGE_THRESHOLD,
    limit: int = 20,
    scan_limit: int = LONG_MEMORY_MERGE_SCAN_LIMIT,
) -> dict[str, Any]:
    """扫描长期记忆的向量相似簇，返回供管理端确认的合并候选。"""

    threshold = max(0.0, min(1.0, threshold))
    limit = min(max(limit, 1), 50)
    memories = fetch_mergeable_long_memory_entries(user_id=user_id, limit=scan_limit)
    clusters = build_similarity_clusters(memories, threshold)

    items: list[dict[str, Any]] = []
    for cluster in clusters[:limit]:
        merge_result = merge_memory_contents(
            [
                {
                    "title": memory["title"],
                    "content": memory["content"],
                    "create_time": memory["create_time"],
                }
                for memory in cluster["memories"]
            ]
        )
        items.append(
            {
                "cluster_id": cluster["cluster_id"],
                "similarity": cluster["similarity"],
                "memory_keys": [memory["memory_key"] for memory in cluster["memories"]],
                "memories": cluster["memories"],
                "suggested_title": merge_result["title"],
                "suggested_content": merge_result["content"],
                "suggested_reason": merge_result["reason"],
            }
        )

    return {
        "items": items,
        "total": len(items),
        "threshold": threshold,
        "scanned": len(memories),
    }


def list_topic_memory_merge_candidates(
    user_id: str,
    topic_query: str,
    threshold: float = 0.52,
    limit: int = 1,
    scan_limit: int = 20,
    max_memories: int = 5,
) -> dict[str, Any]:
    """按明确主题检索长期记忆，并生成主题内的合并建议。"""

    topic = (topic_query or "").strip()[:120]
    threshold = max(0.0, min(1.0, threshold))
    limit = min(max(limit, 1), 3)
    scan_limit = min(max(scan_limit, 2), 80)
    max_memories = min(max(max_memories, 2), 8)
    if not topic:
        return {"items": [], "total": 0, "threshold": threshold, "scanned": 0, "topic": topic}

    store = get_memory_vector_store(LONG_TERM_COLLECTION_NAME)
    try:
        results = store.similarity_search_with_relevance_scores(
            topic,
            k=scan_limit,
            filter={"user_id": user_id},
            score_threshold=threshold,
        )
    except Exception:
        logging.exception("按主题检索长期记忆失败 user_id=%s topic=%s", user_id, topic)
        return {"items": [], "total": 0, "threshold": threshold, "scanned": 0, "topic": topic}

    memories: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for doc, score in sorted(results, key=lambda item: item[1], reverse=True):
        entry = memory_entry_from_document(doc, score)
        if not entry:
            continue
        memory_key = entry["memory_key"]
        if entry.get("user_id") != user_id or memory_key in seen_keys:
            continue
        if not is_memory_retrievable(entry.get("metadata", {}), "long"):
            continue
        seen_keys.add(memory_key)
        memories.append({key: value for key, value in entry.items() if key not in {"metadata"}})
        if len(memories) >= max_memories:
            break

    if len(memories) < 2:
        return {"items": [], "total": 0, "threshold": threshold, "scanned": len(results), "topic": topic}

    items: list[dict[str, Any]] = []
    for index in range(limit):
        if index > 0:
            break
        merge_result = merge_memory_contents(
            [
                {
                    "title": memory["title"],
                    "content": memory["content"],
                    "create_time": memory["create_time"],
                }
                for memory in memories
            ],
            topic_query=topic,
        )
        items.append(
            {
                "cluster_id": "topic-" + "-".join(memory["memory_key"][:8] for memory in memories),
                "topic": topic,
                "relevance": {
                    "max": round(max(float(memory.get("relevance_score") or 0.0) for memory in memories), 4),
                    "min": round(min(float(memory.get("relevance_score") or 0.0) for memory in memories), 4),
                    "avg": round(
                        sum(float(memory.get("relevance_score") or 0.0) for memory in memories) / len(memories),
                        4,
                    ),
                },
                "memory_keys": [memory["memory_key"] for memory in memories],
                "memories": memories,
                "suggested_title": merge_result["title"],
                "suggested_content": merge_result["content"],
                "suggested_reason": merge_result["reason"],
            }
        )

    return {
        "items": items,
        "total": len(items),
        "threshold": threshold,
        "scanned": len(results),
        "topic": topic,
    }


def apply_memory_merge(
    user_id: str,
    memory_keys: list[str],
    merged_title: str,
    merged_content: str,
    reason: str | None = None,
    source: str = "memory_merge_admin",
) -> dict[str, Any]:
    """写入合并后的长期记忆，并把被合并条目标记为 superseded。

    Raises:
        ValueError: 记忆数量不足、条目不属于用户或新记忆保存失败。
    """

    keys = [key.strip() for key in memory_keys if isinstance(key, str) and key.strip()]
    unique_keys = list(dict.fromkeys(keys))
    if len(unique_keys) < 2:
        raise ValueError("at least two memory keys are required")

    rows = fetch_long_memory_entries_by_keys(user_id=user_id, memory_keys=unique_keys)
    if len(rows) < 2:
        raise ValueError("not enough matching active memories to merge")

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
    merge_reason = (reason or "admin_memory_merge")[:160]
    merged_key = save_memory(
        user_id=user_id,
        content=merged_content.strip(),
        title=merged_title.strip()[:80] or "合并记忆",
        create_time=now_text,
        memory_scope="long",
        confidence=max(
            [float(row["confidence"]) for row in rows if isinstance(row.get("confidence"), (float, int))],
            default=0.8,
        ),
        signals=["memory_merge"],
        extra_metadata={
            "source": source,
            "merged_from": unique_keys,
            "merged_at": now_text,
            "merge_reason": merge_reason,
        },
        skip_dedup=True,
    )
    if not merged_key:
        raise ValueError("failed to save merged memory")

    for memory_key in unique_keys:
        mark_memory_superseded(
            user_id=user_id,
            memory_key=memory_key,
            superseded_by=merged_key,
            reason=merge_reason,
        )

    return {
        "memory_key": merged_key,
        "merged_from": unique_keys,
        "title": merged_title.strip()[:80] or "合并记忆",
        "content": merged_content.strip(),
        "reason": merge_reason,
    }


def fetch_mergeable_long_memory_entries(user_id: str, limit: int = LONG_MEMORY_MERGE_SCAN_LIMIT) -> list[dict[str, Any]]:
    """读取指定用户仍处于 active 状态的长期记忆及其向量。"""

    limit = min(max(limit, 2), 1000)
    with SyncSessionLocal() as session:
        result = session.execute(
            select_long_memory_embeddings(user_id=user_id, limit=limit)
        )
        entries = [memory_entry_from_embedding(row) for row in result.scalars().all()]

    return [
        entry
        for entry in entries
        if entry
        and entry.get("user_id") == user_id
        and entry.get("embedding")
        and is_memory_retrievable(entry.get("metadata", {}), "long")
    ]


def fetch_long_memory_entries_by_keys(user_id: str, memory_keys: list[str]) -> list[dict[str, Any]]:
    """按 memory key 精确读取用户长期记忆条目。"""

    key_set = set(memory_keys)
    with SyncSessionLocal() as session:
        result = session.execute(
            select_long_memory_embeddings(user_id=user_id, memory_keys=list(key_set), limit=max(1000, len(key_set)))
        )
        entries = [memory_entry_from_embedding(row) for row in result.scalars().all()]

    return [
        entry
        for entry in entries
        if entry
        and entry.get("memory_key") in key_set
        and is_memory_retrievable(entry.get("metadata", {}), "long")
    ]


def select_long_memory_embeddings(
    limit: int,
    user_id: str | None = None,
    memory_keys: list[str] | None = None,
):
    """构造长期 collection 的 SQLAlchemy embedding 查询。"""

    from sqlalchemy import select

    query = (
        select(LangchainPgEmbedding)
        .join(LangchainPgCollection, LangchainPgEmbedding.collection_id == LangchainPgCollection.uuid)
        .where(LangchainPgCollection.name == LONG_TERM_COLLECTION_NAME)
        .order_by(LangchainPgEmbedding.id.desc())
        .limit(limit)
    )
    if user_id:
        query = query.where(LangchainPgEmbedding.cmetadata["user_id"].astext == user_id)
    if memory_keys:
        query = query.where(LangchainPgEmbedding.cmetadata["memory_key"].astext.in_(memory_keys))
    return query


def memory_entry_from_embedding(row: LangchainPgEmbedding | None) -> dict[str, Any] | None:
    """把 ORM embedding 行转换为合并算法使用的记忆字典。"""

    if row is None:
        return None
    metadata = dict(row.cmetadata or {})
    content = (row.document or "").strip()
    memory_key = metadata.get("memory_key")
    if not content or not isinstance(memory_key, str) or not memory_key:
        return None
    return {
        "id": str(row.id),
        "memory_key": memory_key,
        "user_id": metadata.get("user_id"),
        "title": metadata.get("title") or "未命名记忆",
        "content": content,
        "create_time": metadata.get("create_time"),
        "confidence": metadata.get("confidence"),
        "metadata": metadata,
        "embedding": normalize_embedding(row.embedding),
    }


def memory_entry_from_document(doc: Document, relevance_score: float | None = None) -> dict[str, Any] | None:
    """把 LangChain Document 转换为统一记忆条目。"""

    metadata = dict(doc.metadata or {})
    content = (doc.page_content or "").strip()
    memory_key = metadata.get("memory_key")
    if not content or not isinstance(memory_key, str) or not memory_key:
        return None
    entry = {
        "memory_key": memory_key,
        "user_id": metadata.get("user_id"),
        "title": metadata.get("title") or "未命名记忆",
        "content": content,
        "create_time": metadata.get("create_time"),
        "confidence": metadata.get("confidence"),
        "metadata": metadata,
    }
    if relevance_score is not None:
        entry["relevance_score"] = max(0.0, min(1.0, float(relevance_score)))
    return entry


def normalize_embedding(value: Any) -> list[float]:
    """把 pgvector、numpy 或序列值转换为浮点列表。"""

    if value is None or isinstance(value, (str, bytes, dict)):
        return []
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except (TypeError, ValueError):
            return []
    if not isinstance(value, list):
        try:
            value = list(value)
        except TypeError:
            return []
    normalized: list[float] = []
    for item in value:
        try:
            normalized.append(float(item))
        except (TypeError, ValueError):
            return []
    return normalized


def build_similarity_clusters(memories: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    """用余弦相似度和并查集把相关记忆聚合成候选簇。"""

    parent = list(range(len(memories)))
    pair_scores: dict[tuple[int, int], float] = {}

    def find(index: int) -> int:
        """查找并压缩并查集节点的根索引。"""

        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        """合并两个相似记忆所在的并查集。"""

        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index in range(len(memories)):
        left_embedding = memories[left_index].get("embedding") or []
        for right_index in range(left_index + 1, len(memories)):
            right_embedding = memories[right_index].get("embedding") or []
            score = cosine_similarity(left_embedding, right_embedding)
            if score >= threshold:
                pair_scores[(left_index, right_index)] = score
                union(left_index, right_index)

    grouped: dict[int, list[int]] = {}
    for index in range(len(memories)):
        grouped.setdefault(find(index), []).append(index)

    clusters: list[dict[str, Any]] = []
    for indexes in grouped.values():
        if len(indexes) < 2:
            continue
        scores = [
            pair_scores[(min(left, right), max(left, right))]
            for left in indexes
            for right in indexes
            if left < right and (left, right) in pair_scores
        ]
        if not scores:
            continue
        cluster_memories = [
            {key: value for key, value in memories[index].items() if key not in {"embedding", "metadata"}}
            for index in indexes
        ]
        clusters.append(
            {
                "cluster_id": "cluster-" + "-".join(memory["memory_key"][:8] for memory in cluster_memories),
                "similarity": {
                    "max": round(max(scores), 4),
                    "min": round(min(scores), 4),
                    "avg": round(sum(scores) / len(scores), 4),
                },
                "memories": cluster_memories,
            }
        )

    clusters.sort(key=lambda item: item["similarity"]["max"], reverse=True)
    return clusters


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算等长向量的余弦相似度；空向量或零模长返回 0。"""

    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def search_memory(user_id: str, query: str, k: int = 5, memory_scope: MemoryScope = "all") -> list[Document]:
    """按指定层级检索记忆，并返回合并排序后的文档列表。"""

    layered = search_layered_memories(user_id=user_id, query=query, k=k)
    if memory_scope == "long":
        return layered["long"][:k]
    if memory_scope == "mid":
        return layered["mid"][:k]
    return (layered["long"] + layered["mid"])[:k]


def search_layered_memories(user_id: str, query: str, k: int = 5) -> dict[str, list[Document]]:
    """分别检索长期和中期 collection，保留层级边界。"""

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
    """检索单个 collection，并执行状态过滤、排序和召回触碰。"""

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
            "检索记忆集合失败 scope=%s user_id=%s query=%s",
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
    """不做语义检索，按用户列出指定 collection 的可用记忆。"""

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
    """检索相关记忆并格式化为主模型可引用的上下文文本。"""

    layered = search_layered_memories(user_id=user_id, query=query, k=k)
    sections: list[str] = []
    if layered["long"]:
        sections.append("稳定记忆（只在当前话题确实相关时自然使用）：\n" + format_docs(layered["long"]))
    if layered["mid"]:
        sections.append("近期线索（可能已经变化，使用前结合当前对话判断）：\n" + format_docs(layered["mid"]))
    if not sections:
        return "没有检索到可引用的长期或中期记忆。不要编造用户偏好、天气、城市、食物或共同经历。"
    return "\n\n".join(sections)


def format_docs(docs: list[Document]) -> str:
    """把 Document 列表格式化为带视角和事实层标签的纯文本。

    ``imagined``、``wish`` 和 ``promise`` 必须显式展示标签，避免主模型把共同
    想象、愿望或尚未兑现的承诺误说成现实经历。旧记忆没有字段时按用户现实事实
    处理，以兼容迁移前已经存在的向量文档。
    """

    lines: list[str] = []
    perspective_labels = {"user": "小乔视角", "aura": "Aura 视角", "shared": "共同视角"}
    world_layer_labels = {
        "reality": "现实",
        "shared_history": "真实共同经历",
        "imagined": "共同想象",
        "wish": "愿望",
        "promise": "承诺",
    }
    for doc in docs:
        title = doc.metadata.get("title") or "未命名记忆"
        create_time = doc.metadata.get("create_time") or "未知时间"
        perspective = perspective_labels.get(doc.metadata.get("perspective"), "小乔视角")
        world_layer = world_layer_labels.get(doc.metadata.get("world_layer"), "现实")
        lines.append(
            f"- [{perspective}/{world_layer}] {title}（记录于 {create_time}）：{doc.page_content}"
        )
    return "\n".join(lines)


def list_memories_by_user(
    user_id: str,
    page: int = 1,
    page_size: int = 10,
    memory_scope: MemoryScope = "long",
    include_inactive: bool = False,
) -> dict[str, Any]:
    """分页列出用户记忆，支持层级和 inactive 状态过滤。"""

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
    """通过原生 SQL 读取 collection 内指定用户的记忆正文和 metadata。"""

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
    """返回个人永久记忆和中期记忆策略的 API 描述。"""

    return {
        "plan": "personal",
        "planLabel": "个人永久记忆",
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
            "promotionRecallThreshold": None,
            "policy": "explicit_review",
            "policyLabel": "只有明确重要或人工整理后才转为长期记忆",
        },
        "shortTerm": {
            "source": "chat_history",
        },
    }


def delete_memory_by_id(user_id: str, memory_id: str) -> bool:
    """按 memory key 删除属于用户的一条记忆。"""

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
    """删除用户指定层级的全部向量记忆，并返回删除数量。"""

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
    """根据状态、遗忘时间和晋升标记判断记忆是否仍可被召回。"""

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
    """结合相关度、层级、冷却期和查询意图排序检索结果。"""

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
    """判断用户是否明确要求回忆某件过去信息。"""

    normalized = (query or "").strip().lower()
    return any(keyword in normalized for keyword in EXPLICIT_MEMORY_LOOKUP_KEYWORDS)


def is_memory_catalog_lookup(query: str) -> bool:
    """判断用户是否在请求完整或大范围记忆目录。"""

    normalized = (query or "").strip().lower()
    return any(keyword in normalized for keyword in MEMORY_CATALOG_LOOKUP_KEYWORDS)


def is_long_memory_in_cooldown(metadata: dict[str, Any], now: datetime | None = None) -> bool:
    """判断长期记忆是否处于近期已召回的冷却窗口。"""

    last_recalled_at = parse_memory_create_time(metadata.get("last_recalled_at"))
    if last_recalled_at is None:
        return False

    now = now or datetime.now()
    return now - last_recalled_at < timedelta(minutes=LONG_MEMORY_RECALL_COOLDOWN_MINUTES)


def touch_recalled_memories(user_id: str, docs: list[Document], collection_name: str) -> None:
    """提取召回文档的 memory key，并更新其召回时间和次数。"""

    memory_keys = [
        doc.metadata.get("memory_key")
        for doc in docs
        if isinstance(doc.metadata.get("memory_key"), str)
    ]
    if not memory_keys:
        return

    touch_memory_keys(user_id=user_id, memory_keys=memory_keys, collection_name=collection_name)


def touch_memory_keys(user_id: str, memory_keys: list[str], collection_name: str) -> None:
    """通过原生 SQL 批量更新记忆的召回时间和次数。"""

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
    """更新被召回中期记忆的生命周期字段。"""

    touch_recalled_memories(user_id, docs, MEDIUM_TERM_COLLECTION_NAME)


def mark_memory_superseded(user_id: str, memory_key: str, superseded_by: str, reason: str) -> None:
    """把旧长期记忆标记为已被新记忆替代。"""

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
        logging.exception("标记长期记忆已替代失败 user_id=%s memory_key=%s", user_id, memory_key)


def promote_mid_term_memories(user_id: str, memory_keys: list[str]) -> None:
    """把满足条件的中期记忆写入长期层，并标记原条目已晋升。"""

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
            title=str(metadata.get("title") or "近期线索"),
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
    """读取仍可晋升且属于用户的中期记忆。"""

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
        logging.exception("读取可晋升中期记忆失败 user_id=%s", user_id)
        return []


def mark_mid_memory_promoted(user_id: str, memory_key: str, promoted_memory_key: str) -> None:
    """记录中期记忆对应的长期 key，并停止再次召回。"""

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
        logging.exception("标记中期记忆已晋升失败 user_id=%s memory_key=%s", user_id, memory_key)


def parse_memory_create_time(value: Any) -> datetime | None:
    """解析 metadata 中常见的 ISO 或分钟级创建时间。"""

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
    """返回记忆排序时间；缺失时间使用最早 UTC 时间。"""

    return (
        parse_memory_create_time(metadata.get("last_recalled_at"))
        or parse_memory_create_time(metadata.get("create_time"))
        or datetime.min
    )


def collection_name_for_scope(memory_scope: MemoryScope | Literal["long", "mid"]) -> str:
    """把记忆层级映射到对应的 PGVector collection 名称。"""

    return MEDIUM_TERM_COLLECTION_NAME if memory_scope == "mid" else LONG_TERM_COLLECTION_NAME
