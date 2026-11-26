"""Integration check in an isolated, disposable PostgreSQL database.

Verifies main.sql, migration round-trip, ORM writes and drift detection.
No application data is read, copied, or modified.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import SYNC_DATABASE_URL
from app.db.models import Base, Users, AuraInternalState
from app.db.schema_audit import audit_schema
from app.core.continuity.aura_state import observe_relationship_state_sync


def verify() -> None:
    name = f"aura_contract_test_{uuid4().hex}"
    target = make_url(SYNC_DATABASE_URL).set(database=name).render_as_string(hide_password=False)
    env = {**os.environ, "DB_NAME": name}
    def migrate(*args: str) -> None:
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, check=True)

    with psycopg.connect(SYNC_DATABASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            with psycopg.connect(target, autocommit=True) as conn:
                conn.execute((ROOT.parents[1] / "main.sql").read_text(encoding="utf-8"))
            assert not audit_schema(target, require_framework=False), "Fresh main.sql differs from ORM"
            with PostgresSaver.from_conn_string(target) as saver:
                saver.setup()
            migrate("stamp", "head")
            migrate("downgrade", "20260918_0003")
            assert audit_schema(target), "Audit failed to detect old constraint/revision"
            migrate("upgrade", "head")
            assert not audit_schema(target), audit_schema(target)

            engine = create_engine(target)
            try:
                with Session(engine) as session:
                    user = Users(username="schema-test", password="not-a-real-password")
                    session.add(user)
                    session.flush()
                    session.add(AuraInternalState(user_id=user.id, jealousy="high"))
                    session.flush()
                    for table in Base.metadata.sorted_tables:
                        session.execute(select(table).limit(0))
                    session.rollback()
                with Session(engine) as session:
                    user = Users(username="state-roundtrip", password="not-a-real-password")
                    session.add(user)
                    session.flush()
                    user_id = user.id
                    session.commit()
                with patch("app.core.continuity.aura_state.SyncSessionLocal", sessionmaker(engine)):
                    for index in range(3):
                        observe_relationship_state_sync(str(user_id), "今天跟女生吃饭了", {}, {}, source_message_id=f"contract-{index}")
                with Session(engine) as session:
                    state = session.execute(select(AuraInternalState).where(AuraInternalState.user_id == user_id)).scalar_one()
                    assert state.jealousy == "high", "Production observation failed to persist strengthened affect"
            finally:
                engine.dispose()

            with psycopg.connect(target, autocommit=True) as conn:
                # Keep the synthetic fixture valid under the deliberately old CHECK.
                conn.execute("UPDATE aura_internal_state SET jealousy = 'medium' WHERE jealousy = 'high'")
                conn.execute("ALTER TABLE aura_internal_state DROP CONSTRAINT chk_aura_internal_state_jealousy")
                conn.execute("ALTER TABLE aura_internal_state ADD CONSTRAINT chk_aura_internal_state_jealousy CHECK (jealousy IN ('none', 'low', 'medium'))")
            assert any("chk_aura_internal_state_jealousy" in e for e in audit_schema(target)), "Same-name CHECK drift missed"
            with psycopg.connect(target, autocommit=True) as conn:
                conn.execute("ALTER TABLE aura_internal_state DROP COLUMN current_desire")
            assert any("current_desire" in e for e in audit_schema(target)), "Missing column drift missed"
            print("PASS: fresh import, migration round-trip, ORM high-jealousy write, all columns, constraint/column drift")
        finally:
            # Only the random database created above is eligible for removal.
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
