from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "__pycache__", ".idea", ".jbeval"}
TEXT_SUFFIXES = {".py", ".md"}
MOJIBAKE_MARKERS = (
    "Ã",
    "Â",
    "Ð",
    "Ñ",
    "�",
    "鍙",
    "涓",
    "鎴",
    "鏄",
    "浣",
    "鐢",
    "绋",
    "璁",
    "鐨",
    "浜",
)


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path == Path(__file__).resolve():
            continue
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            files.append(path)
    return files


def main() -> int:
    findings: list[str] = []
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            markers = [marker for marker in MOJIBAKE_MARKERS if marker in line]
            if markers:
                rel = path.relative_to(ROOT)
                marker_text = ",".join(markers)
                detail = f"{rel}:{line_no}: markers={marker_text}: {line.strip()}"
                findings.append(detail.encode("unicode_escape").decode("ascii"))

    if findings:
        print("Potential mojibake found:")
        print("\n".join(findings))
        return 1

    print("No common mojibake markers found in ai-service source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
