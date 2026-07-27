from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models import Base


CREATE_TABLE_PATTERN = re.compile(r"^CREATE TABLE IF NOT EXISTS ([a-z_]+)", re.MULTILINE)


class MainSqlSchemaTests(unittest.TestCase):
    def test_main_sql_covers_every_current_orm_table(self) -> None:
        sql = (REPOSITORY_ROOT / "main.sql").read_text(encoding="utf-8")
        sql_tables = set(CREATE_TABLE_PATTERN.findall(sql))

        self.assertEqual(sql_tables, set(Base.metadata.tables))
        self.assertNotIn("DROP TABLE", sql)

    def test_focus_migration_contains_both_focus_tables(self) -> None:
        sql = (ROOT / "sql" / "20260724_focus_sessions.sql").read_text(encoding="utf-8")

        self.assertEqual(
            {"focus_session", "focus_session_event"},
            set(CREATE_TABLE_PATTERN.findall(sql)),
        )
        self.assertIn("uq_focus_session_running_user", sql)


if __name__ == "__main__":
    unittest.main()
