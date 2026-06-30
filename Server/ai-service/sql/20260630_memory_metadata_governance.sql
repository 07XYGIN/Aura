-- Aura memory governance fields live in langchain_pg_embedding.cmetadata JSONB.
-- This migration does not add physical columns to LangChain-managed tables.

DO $$
BEGIN
    IF to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_memory_user_key
        ON langchain_pg_embedding ((cmetadata ->> 'user_id'), (cmetadata ->> 'memory_key'));

        CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_memory_status
        ON langchain_pg_embedding ((cmetadata ->> 'status'));

        CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_memory_supersedes
        ON langchain_pg_embedding ((cmetadata ->> 'supersedes'))
        WHERE cmetadata ? 'supersedes';

        CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_memory_recall_count
        ON langchain_pg_embedding (((cmetadata ->> 'recall_count')::int))
        WHERE cmetadata ->> 'recall_count' ~ '^[0-9]+$';

        CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_memory_promoted
        ON langchain_pg_embedding ((cmetadata ->> 'promoted_to_long'))
        WHERE cmetadata ? 'promoted_to_long';
    END IF;
END $$;
