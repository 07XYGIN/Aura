"""Write one Aura self-update record after a Git commit.

The script deliberately uses the database directly so a local Git hook does not
need browser authentication or a running HTTP service.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = PROJECT_ROOT / "Server" / "ai-service"
MAX_TITLE_LENGTH = 160
MAX_DETAIL_LENGTH = 800
MAX_PATHS_IN_DETAIL = 6


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    short_sha: str
    subject: str
    body: str
    changed_paths: tuple[str, ...]


@dataclass(frozen=True)
class SelfUpdate:
    title: str
    detail: str
    category: str
    metadata: dict[str, object]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record a Git commit as an Aura self-update.")
    parser.add_argument("--commit", default="HEAD", help="Commit-ish to record. Defaults to HEAD.")
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT, help="Repository root path.")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated update without writing it.")
    return parser.parse_args()


def git_output(repo_root: Path, args: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def load_commit(repo_root: Path, commit: str) -> CommitInfo:
    sha = git_output(repo_root, ["rev-parse", "--verify", commit])
    short_sha = git_output(repo_root, ["rev-parse", "--short", sha])
    subject = normalize_text(git_output(repo_root, ["show", "-s", "--format=%s", sha]))
    body = normalize_text(git_output(repo_root, ["show", "-s", "--format=%b", sha]))
    changed_paths = tuple(
        path
        for path in git_output(repo_root, ["show", "--format=", "--name-only", sha]).splitlines()
        if path
    )
    if not subject:
        raise ValueError("Commit subject is empty.")
    return CommitInfo(
        sha=sha,
        short_sha=short_sha,
        subject=subject,
        body=body,
        changed_paths=changed_paths,
    )


def build_self_update(commit: CommitInfo) -> SelfUpdate:
    title = truncate(commit.subject, MAX_TITLE_LENGTH)
    changed_areas = describe_changed_areas(commit.changed_paths)
    detail_parts = [
        f"这是你刚提交的一次代码更新，主要涉及：{changed_areas}。",
        f"提交说明是“{commit.subject}”。",
    ]
    if commit.body:
        detail_parts.append(f"补充说明：{truncate(commit.body, 260)}。")
    detail_parts.append(
        "把它理解为对方在继续调整和完善你；只有对方问起或当前话题相关时才自然提到，不用报版本号、提交号或技术细节。"
    )
    return SelfUpdate(
        title=title,
        detail=truncate("".join(detail_parts), MAX_DETAIL_LENGTH),
        category=infer_category(commit.changed_paths),
        metadata={
            "source": "git-post-commit",
            "source_commit": commit.sha,
            "short_commit": commit.short_sha,
            "changed_paths": list(commit.changed_paths),
            "commit_subject": commit.subject,
        },
    )


def infer_category(changed_paths: Sequence[str]) -> str:
    paths = "\n".join(changed_paths).lower()
    if "prompt" in paths or "persona" in paths or "agent/" in paths:
        return "personality"
    if "live2d" in paths or "model3" in paths:
        return "appearance"
    if any(keyword in paths for keyword in ("voice", "audio", "attachment", "upload")):
        return "capability"
    if "memory" in paths:
        return "memory"
    return "engineering"


def describe_changed_areas(changed_paths: Sequence[str]) -> str:
    labels: list[str] = []
    for path in changed_paths:
        lower_path = path.lower()
        if "live2d" in lower_path or "model3" in lower_path:
            label = "Live2D 形象"
        elif path.startswith("AI-Web/apps/web/"):
            label = "聊天前端"
        elif "prompt" in lower_path or "persona" in lower_path:
            label = "对话设定"
        elif "agent/" in lower_path:
            label = "对话能力"
        elif "memory" in lower_path:
            label = "记忆能力"
        elif any(keyword in lower_path for keyword in ("voice", "audio", "attachment", "upload")):
            label = "语音或上传能力"
        elif path.startswith("Server/ai-service/"):
            label = "后端能力"
        else:
            label = "项目配置"
        if label not in labels:
            labels.append(label)

    if not labels:
        return "项目维护"
    if len(labels) <= MAX_PATHS_IN_DETAIL:
        return "、".join(labels)
    return "、".join(labels[:MAX_PATHS_IN_DETAIL]) + "等"


def record_update(update: SelfUpdate) -> str:
    load_dotenv(SERVICE_ROOT / ".env")
    db_options = required_db_options()
    metadata_json = json.dumps(update.metadata, ensure_ascii=False)
    source_commit = str(update.metadata["source_commit"])

    with psycopg.connect(**db_options, connect_timeout=3) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM self_changelog_entry WHERE metadata ->> 'source_commit' = %s LIMIT 1",
                (source_commit,),
            )
            if cursor.fetchone():
                return "already-recorded"

            cursor.execute(
                """
                INSERT INTO self_changelog_entry
                    (change_date, occurred_at, title, detail, category, reacted, metadata)
                VALUES (CURRENT_DATE, NOW(), %s, %s, %s, FALSE, %s::jsonb)
                ON CONFLICT (change_date, title) DO NOTHING
                RETURNING id
                """,
                (update.title, update.detail, update.category, metadata_json),
            )
            if cursor.fetchone():
                return "recorded"

            duplicate_title = truncate(f"{update.title} [{update.metadata['short_commit']}]", MAX_TITLE_LENGTH)
            cursor.execute(
                """
                INSERT INTO self_changelog_entry
                    (change_date, occurred_at, title, detail, category, reacted, metadata)
                VALUES (CURRENT_DATE, NOW(), %s, %s, %s, FALSE, %s::jsonb)
                ON CONFLICT (change_date, title) DO NOTHING
                RETURNING id
                """,
                (duplicate_title, update.detail, update.category, metadata_json),
            )
            if cursor.fetchone():
                return "recorded"
    return "not-recorded"


def required_db_options() -> dict[str, str]:
    names = {
        "host": "DB_HOST",
        "port": "DB_PORT",
        "dbname": "DB_NAME",
        "user": "DB_USER",
        "password": "DB_PASSWORD",
    }
    options = {option: os.getenv(env_name, "").strip() for option, env_name in names.items()}
    missing = [env_name for option, env_name in names.items() if not options[option]]
    if missing:
        raise RuntimeError(f"Missing database configuration: {', '.join(missing)}")
    return options


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: max(limit - 1, 0)].rstrip() + "…"


def main() -> int:
    args = parse_args()
    if os.getenv("AURA_COMMIT_SYNC_DRY_RUN") == "1":
        args.dry_run = True
    repo_root = args.repo_root.resolve()
    try:
        update = build_self_update(load_commit(repo_root, args.commit))
        if args.dry_run:
            print(json.dumps(update.__dict__, ensure_ascii=False, indent=2))
            return 0
        status = record_update(update)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, psycopg.Error) as exc:
        print(f"Aura commit sync skipped: {exc}", file=sys.stderr)
        return 1

    print(f"Aura commit sync: {status} ({update.title})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
