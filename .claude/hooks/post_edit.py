"""PostToolUse for Edit/Write/MultiEdit on Python files.

Runs ruff format + ruff check --fix on the edited file, then enforces the
300-line limit after edits. Exit 2 feeds the problem back to Claude.
Silently skips when ruff is not installed yet (before Session 1 bootstrap).
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

MAX_LINES = 300


def find_ruff(file: Path) -> str | None:
    """Prefer the ruff inside the nearest .venv (worktree), else PATH."""
    for parent in file.resolve().parents:
        for rel in (".venv/Scripts/ruff.exe", ".venv/bin/ruff"):
            cand = parent / rel
            if cand.exists():
                return str(cand)
        if (parent / ".git").exists():
            break
    return shutil.which("ruff")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    path = (data.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py") or ".claude" in Path(path).parts:
        sys.exit(0)
    file = Path(path)
    if not file.exists():
        sys.exit(0)

    problems = []
    ruff = find_ruff(file)
    if ruff:
        subprocess.run([ruff, "format", "-q", str(file)], check=False)
        res = subprocess.run(
            [ruff, "check", "--fix", "-q", str(file)], capture_output=True, text=True, check=False
        )
        if res.returncode != 0:
            problems.append(res.stdout.strip() or res.stderr.strip())

    lines = len(file.read_text(encoding="utf-8").splitlines())
    if lines > MAX_LINES:
        problems.append(f"{file.name} has {lines} lines (limit {MAX_LINES}). Split it.")

    if problems:
        print("post_edit.py:\n" + "\n".join(problems), file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
