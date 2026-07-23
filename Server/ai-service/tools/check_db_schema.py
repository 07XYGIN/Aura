from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.core.config import SYNC_DATABASE_URL
from app.db.models import Base


FRAMEWORK_TABLES = {
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
}
POSTGRES_DIALECT = postgresql.dialect()
DELETE_ACTIONS = {
    "a": "NO ACTION",
    "r": "RESTRICT",
    "c": "CASCADE",
    "n": "SET NULL",
    "d": "SET DEFAULT",
}


def normalize_type(value: str) -> str:
    """统一 PostgreSQL 类型别名和空白，便于模型与数据库直接比较。"""
    normalized = " ".join(value.lower().split())
    aliases = {
        "varchar": "character varying",
        "bool": "boolean",
        "int2": "smallint",
        "int4": "integer",
        "timestamptz": "timestamp with time zone",
    }
    for source, target in aliases.items():
        if normalized == source:
            return target
        if normalized.startswith(f"{source}("):
            return f"{target}{normalized[len(source):]}"
    return normalized


def normalize_default(value: Any) -> str | None:
    """去除默认值表达式的外层括号、类型转换和字符串引号。"""
    if value is None:
        return None
    normalized = " ".join(str(value).strip().split()).lower()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    if "::" in normalized:
        normalized = normalized.split("::", 1)[0].strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
        normalized = normalized[1:-1].replace("''", "'")
    return normalized


def normalize_index_ddl(value: str) -> str:
    """统一索引 DDL 的大小写、schema、默认 btree 和空白格式。"""
    normalized = value.lower().replace('"', "")
    normalized = re.sub(r"\bpublic\.", "", normalized)
    normalized = re.sub(r"\s+using\s+btree\s+(?=\()", " ", normalized)
    return " ".join(normalized.split())


def model_constraints(table) -> dict[str, set[Any]]:
    """提取一张 SQLAlchemy 模型表声明的主键、唯一、检查和外键约束。

    Returns:
        按约束类型分组的可比较集合。
    """
    result: dict[str, set[Any]] = {
        "primary": set(),
        "unique": set(),
        "check": set(),
        "foreign": set(),
    }
    for constraint in table.constraints:
        columns = tuple(column.name for column in constraint.columns)
        if isinstance(constraint, PrimaryKeyConstraint):
            result["primary"].add(columns)
        elif isinstance(constraint, UniqueConstraint):
            result["unique"].add(columns)
        elif isinstance(constraint, CheckConstraint):
            if constraint.name:
                result["check"].add(constraint.name)
        elif isinstance(constraint, ForeignKeyConstraint):
            remote_columns = tuple(element.target_fullname.rsplit(".", 1)[1] for element in constraint.elements)
            remote_tables = {element.target_fullname.rsplit(".", 1)[0] for element in constraint.elements}
            remote_table = next(iter(remote_tables))
            result["foreign"].add(
                (
                    columns,
                    remote_table,
                    remote_columns,
                    (constraint.ondelete or "NO ACTION").upper(),
                )
            )
    return result


def database_constraints(conn, model_tables: set[str]) -> dict[str, dict[str, set[Any]]]:
    """从 PostgreSQL 系统目录读取指定模型表的约束。

    Args:
        conn: psycopg 数据库连接。
        model_tables: 需要检查的业务表名集合。

    Returns:
        以表名和约束类型分组的数据库实际约束。
    """
    result = {
        table_name: {"primary": set(), "unique": set(), "check": set(), "foreign": set()}
        for table_name in model_tables
    }
    rows = conn.execute(
        """
        SELECT
            con.conrelid::regclass::text AS table_name,
            con.conname,
            con.contype,
            ARRAY(
                SELECT att.attname
                FROM unnest(con.conkey) WITH ORDINALITY AS key(attnum, position)
                JOIN pg_attribute att
                  ON att.attrelid = con.conrelid
                 AND att.attnum = key.attnum
                ORDER BY key.position
            ) AS local_columns,
            CASE WHEN con.confrelid = 0 THEN NULL ELSE con.confrelid::regclass::text END AS remote_table,
            ARRAY(
                SELECT att.attname
                FROM unnest(con.confkey) WITH ORDINALITY AS key(attnum, position)
                JOIN pg_attribute att
                  ON att.attrelid = con.confrelid
                 AND att.attnum = key.attnum
                ORDER BY key.position
            ) AS remote_columns,
            con.confdeltype
        FROM pg_constraint con
        WHERE con.connamespace = 'public'::regnamespace
          AND con.conrelid::regclass::text = ANY(%s)
          AND con.contype IN ('p', 'u', 'c', 'f')
        """,
        (list(model_tables),),
    )
    for row in rows:
        table_name = row["table_name"].removeprefix("public.")
        constraint_type = row["contype"]
        if constraint_type == "p":
            result[table_name]["primary"].add(tuple(row["local_columns"] or []))
        elif constraint_type == "u":
            result[table_name]["unique"].add(tuple(row["local_columns"] or []))
        elif constraint_type == "c":
            result[table_name]["check"].add(row["conname"])
        elif constraint_type == "f":
            result[table_name]["foreign"].add(
                (
                    tuple(row["local_columns"] or []),
                    str(row["remote_table"]).removeprefix("public."),
                    tuple(row["remote_columns"] or []),
                    DELETE_ACTIONS[row["confdeltype"]],
                )
            )
    return result


def database_indexes(conn, model_tables: set[str]) -> dict[str, dict[str, str]]:
    """读取不属于约束的普通索引，并返回规范化后的 DDL。"""
    result = {table_name: {} for table_name in model_tables}
    rows = conn.execute(
        """
        SELECT tbl.relname AS table_name, idx.relname AS index_name, pg_get_indexdef(i.indexrelid) AS index_ddl
        FROM pg_index i
        JOIN pg_class idx ON idx.oid = i.indexrelid
        JOIN pg_class tbl ON tbl.oid = i.indrelid
        JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
        LEFT JOIN pg_constraint con ON con.conindid = i.indexrelid
        WHERE ns.nspname = 'public'
          AND tbl.relname = ANY(%s)
          AND con.oid IS NULL
        """,
        (list(model_tables),),
    )
    for row in rows:
        result[row["table_name"]][row["index_name"]] = normalize_index_ddl(row["index_ddl"])
    return result


def main() -> int:
    """比较在线 PostgreSQL 与 SQLAlchemy 模型的完整结构。

    检查业务表、LangGraph 框架表、字段、类型、可空性、默认值、约束和索引。

    Returns:
        完全一致返回 0；发现任一差异并打印明细后返回 1。
    """
    with psycopg.connect(SYNC_DATABASE_URL, row_factory=dict_row) as conn:
        database_tables = {
            row["table_name"]
            for row in conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                """
            )
        }
        business_tables = database_tables - FRAMEWORK_TABLES
        model_tables = set(Base.metadata.tables)

        errors: list[str] = []
        for table_name in sorted(FRAMEWORK_TABLES - database_tables):
            errors.append(f"数据库缺少 LangGraph 框架表：{table_name}")
        for table_name in sorted(model_tables - business_tables):
            errors.append(f"数据库缺少模型表：{table_name}")
        for table_name in sorted(business_tables - model_tables):
            errors.append(f"数据库存在未建模业务表：{table_name}")

        database_column_rows = conn.execute(
            """
            SELECT
                cls.relname AS table_name,
                attr.attname AS column_name,
                pg_catalog.format_type(attr.atttypid, attr.atttypmod) AS formatted_type,
                NOT attr.attnotnull AS nullable,
                pg_get_expr(def.adbin, def.adrelid) AS column_default
            FROM pg_attribute attr
            JOIN pg_class cls ON cls.oid = attr.attrelid
            JOIN pg_namespace ns ON ns.oid = cls.relnamespace
            LEFT JOIN pg_attrdef def
              ON def.adrelid = attr.attrelid
             AND def.adnum = attr.attnum
            WHERE ns.nspname = 'public'
              AND cls.relname = ANY(%s)
              AND attr.attnum > 0
              AND NOT attr.attisdropped
            """,
            (list(model_tables),),
        )
        database_columns = {
            (row["table_name"], row["column_name"]): row
            for row in database_column_rows
        }

        for table_name, table in Base.metadata.tables.items():
            model_columns = set(table.c.keys())
            actual_columns = {
                column_name
                for actual_table, column_name in database_columns
                if actual_table == table_name
            }
            for column_name in sorted(model_columns - actual_columns):
                errors.append(f"数据库缺少字段：{table_name}.{column_name}")
            for column_name in sorted(actual_columns - model_columns):
                errors.append(f"数据库存在未建模字段：{table_name}.{column_name}")

            for column in table.columns:
                row = database_columns.get((table_name, column.name))
                if row is None:
                    continue
                model_type = normalize_type(column.type.compile(dialect=POSTGRES_DIALECT))
                database_type = normalize_type(row["formatted_type"])
                if model_type != database_type:
                    errors.append(
                        f"字段类型不一致：{table_name}.{column.name}，模型={model_type}，数据库={database_type}"
                    )
                if bool(column.nullable) != bool(row["nullable"]):
                    errors.append(
                        f"字段可空性不一致：{table_name}.{column.name}，模型={column.nullable}，数据库={row['nullable']}"
                    )
                model_default = normalize_default(column.server_default.arg if column.server_default else None)
                database_default = normalize_default(row["column_default"])
                if model_default != database_default:
                    errors.append(
                        f"字段默认值不一致：{table_name}.{column.name}，模型={model_default}，数据库={database_default}"
                    )

        actual_constraints = database_constraints(conn, model_tables)
        for table_name, table in Base.metadata.tables.items():
            expected = model_constraints(table)
            actual = actual_constraints[table_name]
            for kind, label in (
                ("primary", "主键"),
                ("unique", "唯一约束"),
                ("check", "检查约束"),
                ("foreign", "外键"),
            ):
                if expected[kind] != actual[kind]:
                    errors.append(
                        f"{label}不一致：{table_name}，模型={sorted(expected[kind], key=str)}，数据库={sorted(actual[kind], key=str)}"
                    )

        actual_indexes = database_indexes(conn, model_tables)
        for table_name, table in Base.metadata.tables.items():
            expected_indexes = {
                index.name: normalize_index_ddl(str(CreateIndex(index).compile(dialect=POSTGRES_DIALECT)))
                for index in table.indexes
            }
            if expected_indexes != actual_indexes[table_name]:
                errors.append(
                    f"普通索引不一致：{table_name}，模型={expected_indexes}，数据库={actual_indexes[table_name]}"
                )

    if errors:
        print("数据库结构检查失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print("数据库表、字段、类型、可空性、默认值、约束、索引与当前模型一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
