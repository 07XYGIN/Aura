ALTER TABLE self_changelog_entry
    ADD COLUMN IF NOT EXISTS occurred_at timestamptz;

UPDATE self_changelog_entry
SET occurred_at = change_date::timestamptz
WHERE occurred_at IS NULL;

ALTER TABLE self_changelog_entry
    ALTER COLUMN occurred_at SET DEFAULT now(),
    ALTER COLUMN occurred_at SET NOT NULL;

ALTER TABLE self_changelog_entry
    ADD COLUMN IF NOT EXISTS category varchar(64) NOT NULL DEFAULT 'infra';

COMMENT ON COLUMN self_changelog_entry.occurred_at IS '改动实际发生时间，支持后台补录和按时间倒序展示';
COMMENT ON COLUMN self_changelog_entry.category IS '更新分类，例如 memory、perception、personality、infra';

CREATE INDEX IF NOT EXISTS idx_self_changelog_occurred_at ON self_changelog_entry(occurred_at DESC);
