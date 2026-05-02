"""
Build checker module.

Performs lightweight syntax and structural verification on generated code
without requiring a full next build. Runs as a subprocess step between
Developer and QA Reviewer.
"""

import asyncio
import json
import re
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import settings
from app.schemas.agent_outputs import BuildCheckIssue, BuildCheckResult, CodeOutput

_REQUIRED_FILES = {"app/layout.js", "app/page.js", "package.json"}
_REQUIRED_DEPS = {"next", "react", "better-sqlite3", "tailwindcss"}


async def run_build_check(code_output: CodeOutput) -> BuildCheckResult:
    """Run syntax + structural checks on generated code. Returns a BuildCheckResult."""
    start = time.monotonic()
    issues: list[BuildCheckIssue] = []
    files_checked = 0

    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Write files to temp dir
        for code_file in code_output.files:
            dest = tmp / code_file.path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(code_file.content, encoding="utf-8")

        # --- Structural checks ---
        present_paths = {f.path for f in code_output.files}

        for required in _REQUIRED_FILES:
            if required not in present_paths:
                issues.append(BuildCheckIssue(
                    file=required,
                    severity="error",
                    message=f"Required file '{required}' is missing from the generated project.",
                    check="missing_required_file",
                ))

        # --- package.json dependency check ---
        pkg_file = next((f for f in code_output.files if f.path == "package.json"), None)
        if pkg_file is not None:
            files_checked += 1
            try:
                pkg = json.loads(pkg_file.content)
                all_deps = set(pkg.get("dependencies", {}).keys()) | set(pkg.get("devDependencies", {}).keys())
                for dep in _REQUIRED_DEPS:
                    if dep not in all_deps:
                        issues.append(BuildCheckIssue(
                            file="package.json",
                            severity="error",
                            message=f"Required dependency '{dep}' is missing from package.json.",
                            check="json_parse",
                        ))
            except json.JSONDecodeError as exc:
                issues.append(BuildCheckIssue(
                    file="package.json",
                    line=exc.lineno,
                    column=exc.colno,
                    severity="error",
                    message=f"package.json is not valid JSON: {exc.msg}",
                    check="json_parse",
                ))

        # --- JSON file syntax checks ---
        for code_file in code_output.files:
            if code_file.language == "json" and code_file.path != "package.json":
                files_checked += 1
                try:
                    json.loads(code_file.content)
                except json.JSONDecodeError as exc:
                    issues.append(BuildCheckIssue(
                        file=code_file.path,
                        line=exc.lineno,
                        column=exc.colno,
                        severity="error",
                        message=f"Invalid JSON: {exc.msg}",
                        check="json_parse",
                    ))

        # --- JavaScript syntax checks via `node --check` ---
        for code_file in code_output.files:
            if code_file.language == "javascript":
                files_checked += 1
                file_path = tmp / code_file.path
                js_issues = await _check_js_syntax(code_file.path, file_path)
                issues.extend(js_issues)

        # --- Full build (disabled by default) ---
        full_build_attempted = False
        full_build_log: str | None = None

        if settings.enable_full_build_check:
            full_build_attempted = True
            full_build_log, build_issues = await _run_full_build(tmp, code_output.project_name)
            issues.extend(build_issues)

    duration_ms = int((time.monotonic() - start) * 1000)
    error_count = sum(1 for i in issues if i.severity == "error")

    return BuildCheckResult(
        passed=error_count == 0,
        duration_ms=duration_ms,
        files_checked=files_checked,
        issues=issues,
        full_build_attempted=full_build_attempted,
        full_build_log=full_build_log,
    )


async def _check_js_syntax(rel_path: str, abs_path: Path) -> list[BuildCheckIssue]:
    """Run `node --check` on a single JS file. Returns list of issues."""
    try:
        proc = await asyncio.create_subprocess_exec(
            settings.build_check_node_path,
            "--check",
            str(abs_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        except asyncio.TimeoutError:
            proc.kill()
            return [BuildCheckIssue(
                file=rel_path,
                severity="error",
                message="Syntax check timed out after 10 seconds.",
                check="syntax_js",
            )]
    except FileNotFoundError:
        # node not found — skip JS checks silently (documented as a requirement)
        return []

    if proc.returncode == 0:
        return []

    return _parse_node_stderr(rel_path, stderr.decode(errors="replace"))


def _parse_node_stderr(rel_path: str, stderr: str) -> list[BuildCheckIssue]:
    """Parse `node --check` stderr into BuildCheckIssue objects."""
    issues: list[BuildCheckIssue] = []
    # node --check output: /abs/path/file.js:12\nSyntaxError: ...
    # Also: /abs/path/file.js:12\n^\n\nSyntaxError: ...
    line_re = re.compile(r":(\d+)$", re.MULTILINE)
    msg_re = re.compile(r"(SyntaxError: .+)$", re.MULTILINE)

    line_match = line_re.search(stderr)
    msg_match = msg_re.search(stderr)

    line_num = int(line_match.group(1)) if line_match else None
    message = msg_match.group(1).strip() if msg_match else stderr.strip()[:200]

    issues.append(BuildCheckIssue(
        file=rel_path,
        line=line_num,
        severity="error",
        message=message,
        check="syntax_js",
    ))
    return issues


async def _run_full_build(tmpdir: Path, project_name: str) -> tuple[str, list[BuildCheckIssue]]:
    """Run npm install + next build in tmpdir. Returns (log, issues)."""
    issues: list[BuildCheckIssue] = []
    logs: list[str] = []

    for cmd in [
        ["npm", "install", "--no-audit", "--prefer-offline"],
        ["npx", "next", "build"],
    ]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(tmpdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=settings.full_build_timeout_seconds,
                )
            except asyncio.TimeoutError:
                proc.kill()
                issues.append(BuildCheckIssue(
                    file=project_name,
                    severity="error",
                    message=f"'{' '.join(cmd)}' timed out after {settings.full_build_timeout_seconds}s.",
                    check="next_build",
                ))
                break

            log_text = stdout.decode(errors="replace")
            logs.append(f"$ {' '.join(cmd)}\n{log_text}")

            if proc.returncode != 0:
                issues.append(BuildCheckIssue(
                    file=project_name,
                    severity="error",
                    message=f"'{' '.join(cmd)}' failed (exit {proc.returncode}). See build log.",
                    check="next_build",
                ))
                break

        except FileNotFoundError:
            issues.append(BuildCheckIssue(
                file=project_name,
                severity="error",
                message=f"Command '{cmd[0]}' not found. Cannot run full build check.",
                check="next_build",
            ))
            break

    return "\n".join(logs), issues
