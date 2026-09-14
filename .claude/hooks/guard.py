"""PreToolUse guard for Edit/Write/MultiEdit and Bash.

Exit 2 blocks the tool call and shows stderr to Claude. Exit 0 allows.
Rules mirror the hard boundaries in CLAUDE.md.
"""

import json
import re
import subprocess
import sys

ALLOWED_DEPS = {"requests", "beautifulsoup4", "lxml", "pyyaml", "playwright", "pytest", "ruff"}
BANNED_IMPORTS = re.compile(
    r"^\s*(import|from)\s+(openai|anthropic|google\.generativeai|google\.genai|groq|langchain\w*|"
    r"mistralai|cohere|ollama|litellm|selenium|scrapy|django|flask|fastapi|sqlalchemy)\b",
    re.MULTILINE,
)
MAX_LINES = 300
PROTECTED = {"main", "master"}


def block(msg: str) -> None:
    print(f"BLOCKED by .claude/hooks/guard.py: {msg}", file=sys.stderr)
    sys.exit(2)


def norm(path: str) -> str:
    return path.replace("\\", "/")


def git(cwd: str, *args: str) -> str:
    try:
        res = subprocess.run(
            ["git", *args], cwd=cwd or None, capture_output=True, text=True, timeout=8
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return res.stdout.strip() if res.returncode == 0 else ""


def remote_main_exists(cwd: str) -> bool:
    try:
        res = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", "main"],
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True  # fail closed
    return res.returncode != 0 or bool(res.stdout.strip())


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


def push_targets_main(cmd: str, cwd: str) -> bool:
    m = re.search(r"git\s+push\b(.*)", cmd)
    args = [a for a in (m.group(1).split("&&")[0].split(";")[0].split() if m else [])]
    refs = [a for a in args if not a.startswith("-")][1:]  # drop remote name
    if not refs or any(r in ("HEAD", "@") for r in refs):
        return git(cwd, "rev-parse", "--abbrev-ref", "HEAD") in PROTECTED
    for r in refs:
        dest = r.split(":")[-1].removeprefix("+").removeprefix("refs/heads/")
        if dest in PROTECTED:
            return True
    return False


def check_bash(tin: dict, cwd: str) -> None:
    cmd = tin.get("command", "")
    if re.search(r"git\s+push\b[^;&|]*(--force|\s-f\b|--force-with-lease|\s\+\S)", cmd):
        block("force push is forbidden.")
    if re.search(r"git\s+push\b[^;&|]*--(delete|mirror)|git\s+push\b[^;&|]*\s:\S", cmd):
        block("deleting or mirroring remote refs is forbidden.")
    if re.search(r"git\s+push\b", cmd) and push_targets_main(cmd, cwd):
        if remote_main_exists(cwd):
            block("main is protected. Push a task branch and open a PR (ship skill).")
    if re.search(r"git\s+commit\b", cmd):
        if git(cwd, "rev-parse", "--abbrev-ref", "HEAD") in PROTECTED and remote_main_exists(cwd):
            block("do not commit on main. Work in the task worktree branch.")
    if re.search(r"git\s+(reset\s+--hard|clean\s+-\w*f|checkout\s+--\s+\.|restore\s+\.)", cmd):
        block("destructive git command. Ask the owner.")
    if re.search(r"gh\s+pr\s+merge\b", cmd):
        if "--admin" in cmd:
            block("--admin bypasses branch protection. Wait for CI.")
        if "--squash" not in cmd:
            block("merge with --squash only.")
    if re.search(r"gh\s+(repo\s+(delete|archive|rename)|release\s+delete)\b", cmd):
        block("repo-level destructive gh command. Owner only.")
    if re.search(r"gh\s+api\b", cmd) and re.search(r"(-X|--method)\s*(DELETE|PUT|PATCH|POST)", cmd):
        if re.search(r"protection|rulesets|/collaborators|/keys|/hooks|/secrets", cmd):
            block("changing repo protection, access, hooks or secrets is owner only.")
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
        check_bash(tin, data.get("cwd", ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
