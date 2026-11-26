import unittest
from unittest.mock import patch, MagicMock

from app.db.schema_audit import assert_schema_ready
from app.core.auth_store import users_table
from app.db.models import Users


class SchemaStartupTest(unittest.TestCase):
    def test_auth_uses_the_authoritative_table(self):
        self.assertIs(users_table, Users.__table__)

    def test_mismatch_stops_startup_with_actionable_error(self):
        with patch("app.db.schema_audit.audit_schema", return_value=["missing aura_internal_state.jealousy"]):
            with self.assertRaisesRegex(RuntimeError, "aura_internal_state.jealousy"):
                assert_schema_ready()

    def test_aligned_schema_allows_startup(self):
        with patch("app.db.schema_audit.audit_schema", return_value=[]):
            assert_schema_ready()


class LifespanSchemaTest(unittest.IsolatedAsyncioTestCase):
    async def test_schema_failure_prevents_graph_and_scheduler_start(self):
        import main
        saver = MagicMock()
        with (
            patch.object(main.PostgresSaver, "from_conn_string", return_value=saver),
            patch.object(main, "assert_schema_ready", side_effect=RuntimeError("missing-column")),
            patch.object(main.agent_graph, "build_graph") as build,
            patch.object(main, "start_proactive_scheduler") as scheduler,
        ):
            with self.assertRaisesRegex(RuntimeError, "missing-column"):
                async with main.lifespan(main.create_app()):
                    self.fail("Invalid schema must never serve requests")
            build.assert_not_called()
            scheduler.assert_not_called()
