"""PreToolUse guard for Edit/Write/MultiEdit and Bash.

Exit 2 blocks the tool call and shows stderr to Claude. Exit 0 allows.
Rules mirror the hard boundaries in CLAUDE.md.
"""

import json
import re
import sys

ALLOWED_DEPS = {"requests", "beautifulsoup4", "lxml", "pyyaml", "playwright", "pytest", "ruff"}
BANNED_IMPORTS = re.compile(
    r"^\s*(import|from)\s+(openai|anthropic|google\.generativeai|google\.genai|groq|langchain\w*|"
    r"mistralai|cohere|ollama|litellm|selenium|scrapy|django|flask|fastapi|sqlalchemy)\b",
    re.MULTILINE,
)
MAX_LINES = 300


def block(msg: str) -> None:
    print(f"BLOCKED by .claude/hooks/guard.py: {msg}", file=sys.stderr)
    sys.exit(2)


def norm(path: str) -> str:
    return path.replace("\\", "/")


def new_content(tool: str, tin: dict) -> str:
    if tool == "Write":
        return tin.get("content", "")
    if tool == "Edit":
        return tin.get("new_string", "")
    if tool == "MultiEdit":
        return "\n".join(e.get("new_string", "") for e in tin.get("edits", []))
    return ""


def check_file_tool(tool: str, tin: dict) -> None:
    path = norm(tin.get("file_path", ""))
    name = path.rsplit("/", 1)[-1]
    content = new_content(tool, tin)

    if re.search(r"(^|/)state/", path) and "/tests/" not in path:
        block("state/ is bot-written. Use tests/fixtures or tmp_path in tests.")
    if name == ".env" or name.endswith(".docx") or name.endswith(".pem"):
        block(f"{name} is a secret or source document. Do not edit via Claude.")
    if re.search(r"hooks\.slack\.com/services/[A-Z0-9]+/", content):
        block("Slack webhook URL in file content. Use the SLACK_WEBHOOK_URL secret.")
    if re.search(r"gh[pousr]_[A-Za-z0-9]{30,}", content):
        block("GitHub token in file content. Use secrets.")

    if path.endswith(".py") and "/.claude/" not in path and BANNED_IMPORTS.search(content):
        block("AI SDK / framework import is out of scope (CLAUDE.md hard boundaries).")

    if name.startswith("requirements") and name.endswith(".txt"):
        for line in content.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or line.startswith("-r"):
                continue
            pkg = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0].lower()
            if pkg not in ALLOWED_DEPS:
                block(f"dependency '{pkg}' not in the approved list. Ask the owner first.")

    if tool == "Write" and path.endswith(".py") and content.count("\n") + 1 > MAX_LINES:
        block(f"{name} would exceed {MAX_LINES} lines. Split by responsibility.")


def check_bash(tin: dict) -> None:
    cmd = tin.get("command", "")
    if re.search(r"git\s+push\b.*(--force|-f\b|--force-with-lease)", cmd):
        block("force push is forbidden.")
    if re.search(r"git\s+push\b", cmd):
        block("push only when the owner asks in chat; ask, then the owner runs or approves it.")
    throwaway = re.search(r"scratchpad|[\\/]Temp[\\/]", cmd, re.IGNORECASE)
    if not throwaway and re.search(
        r"\bpip\s+install\b(?!\s+(-r|--requirement|-e\s+\.|--upgrade\s+pip))", cmd
    ):
        block("ad-hoc pip install. Add approved deps to requirements*.txt, then pip install -r.")
    if re.search(r"(rm\s+-rf?|Remove-Item).*\bstate\b", cmd):
        block("deleting state/ is forbidden.")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    tool = data.get("tool_name", "")
    tin = data.get("tool_input", {}) or {}
    if tool in ("Write", "Edit", "MultiEdit"):
        check_file_tool(tool, tin)
    elif tool == "Bash":
        check_bash(tin)
    sys.exit(0)


if __name__ == "__main__":
    main()
