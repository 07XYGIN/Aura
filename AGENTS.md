# Aura repository instructions

## Database contract

- `main.sql` at the repository root is the only `.sql` file allowed in this project. It must always describe the complete current PostgreSQL business schema for a fresh import.
- Do not add dated SQL files or a second schema dump. Historical and incremental upgrades belong in `Server/ai-service/alembic/versions/` as Alembic Python revisions.
- Whenever a task changes SQLAlchemy tables, columns, constraints, indexes, PostgreSQL extensions, or removes a database-backed feature, update all of the following in the same task:
  1. `Server/ai-service/app/db/models.py`;
  2. the canonical root `main.sql`;
  3. an Alembic revision when an existing database needs an upgrade;
  4. `Server/ai-service/docs/database-schema.md` when table ownership or lifecycle changes.
- After a database-related change, automatically apply the upgrade to the local PostgreSQL configured by `Server/ai-service/.env`, then run `uv run python tools/check_db_schema.py` from `Server/ai-service`.
- Never stamp an Alembic revision until the live schema has been checked. For a fresh database imported from `main.sql`, run `uv run alembic stamp head`; for an existing versioned database, run `uv run alembic upgrade head`.
- Before dropping a table or column, verify its exact name, confirm it has no current runtime/ORM owner, and inspect whether it contains data. Keep LangGraph `checkpoint_*` and LangChain PGVector tables unless their owning subsystem is also removed.

## Verification

- Run `uv run python -m unittest discover -s tests` for backend changes.
- Database changes are incomplete until `main.sql`, Alembic, the live local database, and SQLAlchemy metadata agree.

## Automatic Git delivery

- At the end of every completed conversation turn that changes repository files, automatically commit the completed changes and push the current branch to its configured upstream remote without waiting for another request.
- Before committing, run the checks relevant to the changed files, inspect `git status`, and make sure secrets, local `.env` files, generated caches, and unrelated user work are not accidentally staged.
- Use a concise commit message describing the completed outcome. After pushing, verify that the local branch and its upstream point to the new commit. If committing or pushing fails, do not hide the failure; report the exact blocker to the user.
