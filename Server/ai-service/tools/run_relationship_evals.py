"""Check prewritten response fixtures only; this does NOT evaluate live model output.

For actual generated multi-turn responses use run_relationship_conversations.py --live.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.evals import load_eval_scenarios, run_eval_suite


FIXTURE = ROOT / "tests" / "fixtures" / "aura_relationship_eval_cases.json"


if __name__ == "__main__":
    report = run_eval_suite(load_eval_scenarios(FIXTURE))
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    raise SystemExit(0 if report.failed == 0 else 1)
