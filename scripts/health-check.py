#!/usr/bin/env python3
"""Health check for claude-code-bmad-foundation.

Run once after deriving the template to verify the environment is wired up.
Run anytime later to catch drift.

Usage:
    python scripts/health-check.py

Exit codes:
    0 = all checks passed (warnings are non-fatal)
    1 = at least one FAIL check failed
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

USE_COLOR = sys.stdout.isatty()


def _color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


PASS = _color("PASS", "32")
WARN = _color("WARN", "33")
FAIL = _color("FAIL", "31")


class Counter:
    fails = 0
    warns = 0


def report(status: str, name: str, detail: str = "") -> None:
    if "FAIL" in status:
        Counter.fails += 1
    elif "WARN" in status:
        Counter.warns += 1
    line = f"  {status}  {name}"
    if detail:
        line += f"  - {detail}"
    print(line)


def check_file(path: Path, name: str) -> None:
    if path.is_file():
        report(PASS, name)
    else:
        rel = path.relative_to(REPO_ROOT)
        report(FAIL, name, f"missing at {rel}")


def check_dir(path: Path, name: str) -> None:
    if path.is_dir():
        report(PASS, name)
    else:
        rel = path.relative_to(REPO_ROOT)
        report(FAIL, name, f"missing at {rel}")


def check_json(path: Path, name: str) -> None:
    if not path.is_file():
        rel = path.relative_to(REPO_ROOT)
        report(FAIL, name, f"missing at {rel}")
        return
    try:
        json.loads(path.read_text(encoding="utf-8"))
        report(PASS, name)
    except json.JSONDecodeError as e:
        report(FAIL, name, f"invalid JSON: {e}")


def check_command(cmd: list[str], name: str, warn_on_fail: bool = False) -> None:
    if shutil.which(cmd[0]) is None:
        status = WARN if warn_on_fail else FAIL
        report(status, name, f"`{cmd[0]}` not on PATH")
        return
    # On Windows, .cmd/.bat scripts (pnpm, npx, etc.) need shell=True to run.
    # cmd is hardcoded from main() so shell=True carries no injection risk.
    use_shell = sys.platform == "win32"
    cmd_arg = " ".join(cmd) if use_shell else cmd
    try:
        result = subprocess.run(
            cmd_arg,
            shell=use_shell,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        status = WARN if warn_on_fail else FAIL
        msg = f"errno {e.errno}" if isinstance(e, OSError) and e.errno else str(e)[:80]
        report(status, name, msg)
        return
    if result.returncode == 0:
        first_line = (result.stdout + result.stderr).strip().splitlines()
        version = first_line[0] if first_line else "ok"
        report(PASS, name, version[:60])
    else:
        status = WARN if warn_on_fail else FAIL
        report(status, name, f"exit {result.returncode}")


def check_mcp_server_entry(name: str) -> None:
    mcp_path = REPO_ROOT / ".mcp.json"
    if not mcp_path.is_file():
        report(FAIL, f"MCP entry: {name}", ".mcp.json missing")
        return
    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        report(FAIL, f"MCP entry: {name}", ".mcp.json invalid")
        return
    servers = data.get("mcpServers", {})
    if name in servers:
        report(PASS, f"MCP entry: {name}")
    else:
        report(FAIL, f"MCP entry: {name}", "not declared in .mcp.json")


def main() -> int:
    title = "claude-code-bmad-foundation health check"
    print()
    print(_color(title, "1"))
    print(_color("=" * len(title), "1"))

    print(_color("\n== Core files ==", "1"))
    check_file(REPO_ROOT / "CLAUDE.md", "CLAUDE.md present")
    check_json(REPO_ROOT / ".mcp.json", ".mcp.json parses as JSON")
    check_json(
        REPO_ROOT / ".claude" / "settings.json",
        ".claude/settings.json parses as JSON",
    )
    check_file(
        REPO_ROOT / ".claude" / "hooks" / "block_dangerous_commands.py",
        "Safety hook script present",
    )
    check_file(REPO_ROOT / ".gitignore", ".gitignore present")
    check_file(REPO_ROOT / "LICENSE", "LICENSE present")

    print(_color("\n== MCP servers declared ==", "1"))
    check_mcp_server_entry("context7")
    check_mcp_server_entry("sequential-thinking")

    print(_color("\n== Playwright pre-stage ==", "1"))
    check_json(REPO_ROOT / "package.json", "package.json parses as JSON")
    check_file(REPO_ROOT / "playwright.config.ts", "playwright.config.ts present")
    check_file(REPO_ROOT / "e2e" / "example.spec.ts", "e2e/example.spec.ts present")

    print(_color("\n== BMad install ==", "1"))
    check_dir(REPO_ROOT / "_bmad", "_bmad/ directory present")
    check_file(REPO_ROOT / "_bmad" / "config.toml", "_bmad/config.toml present")

    print(_color("\n== GitHub scaffolding ==", "1"))
    check_file(
        REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
        "PR template present",
    )
    check_file(
        REPO_ROOT / ".github" / "dependabot.yml",
        "Dependabot config present",
    )

    print(_color("\n== Runtime tools ==", "1"))
    check_command([sys.executable, "--version"], "Python")
    check_command(["git", "--version"], "Git")
    check_command(
        ["node", "--version"], "Node.js (Playwright + MCP)", warn_on_fail=True
    )
    check_command(
        ["pnpm", "--version"], "pnpm (Playwright activation)", warn_on_fail=True
    )
    check_command(["npx", "--version"], "npx (MCP runner)", warn_on_fail=True)

    print(_color("\n== Safety hook compiles ==", "1"))
    hook_path = REPO_ROOT / ".claude" / "hooks" / "block_dangerous_commands.py"
    if hook_path.is_file():
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(hook_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            report(FAIL, "Hook compile check", str(e)[:80])
        else:
            if result.returncode == 0:
                report(PASS, "Safety hook compiles cleanly")
            else:
                report(FAIL, "Safety hook compiles", result.stderr.strip()[:80])

    print(_color("\n== Summary ==", "1"))
    if Counter.fails == 0 and Counter.warns == 0:
        print(f"  {_color('All checks passed.', '32')} Environment is ready.")
        print()
        return 0
    if Counter.fails == 0:
        print(f"  {_color(f'{Counter.warns} warning(s)', '33')}, no failures.")
        print("  Warnings usually mean an optional tool is not installed.")
        print()
        return 0
    print(
        f"  {_color(f'{Counter.fails} failure(s)', '31')}, "
        f"{_color(f'{Counter.warns} warning(s)', '33')}."
    )
    print("  Fix the failures before relying on the template.")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
