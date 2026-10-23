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

    def test_repository_has_one_canonical_sql_file(self) -> None:
        ignored_directories = {".git", ".venv", "node_modules", "build", "dist"}
        sql_files = sorted(
            path
            for path in REPOSITORY_ROOT.rglob("*.sql")
            if ignored_directories.isdisjoint(path.relative_to(REPOSITORY_ROOT).parts)
        )

        self.assertEqual(sql_files, [REPOSITORY_ROOT / "main.sql"])

    def test_removed_activity_tables_are_absent_from_current_schema(self) -> None:
        sql = (REPOSITORY_ROOT / "main.sql").read_text(encoding="utf-8")

        for table_name in (
            "focus_session",
            "focus_session_event",
            "bash_game_session",
            "bash_game_move",
            "companion_pet",
            "pet_event",
        ):
            self.assertNotIn(f"CREATE TABLE IF NOT EXISTS {table_name}", sql)


if __name__ == "__main__":
    unittest.main()
