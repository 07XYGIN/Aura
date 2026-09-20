"""Check the live database using the same audit as application startup."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.schema_audit import audit_schema


def main() -> int:
    errors = audit_schema()
    if errors:
        print("数据库结构检查失败：\n" + "\n".join(f"- {item}" for item in errors))
        return 1
    print("数据库列、类型、默认值、约束内容、索引和迁移版本与后端一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
