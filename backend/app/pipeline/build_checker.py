"""
Build checker module.

Performs syntax + structural verification (always on) and an optional full
`next build` against a pre-seeded sandbox (gated by enable_full_build_check).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import settings
from app.schemas.agent_outputs import BuildCheckIssue, BuildCheckResult, CodeOutput

_REQUIRED_FILES = {"app/layout.js", "app/page.js", "package.json"}
_REQUIRED_DEPS = {"next", "react", "better-sqlite3", "tailwindcss"}
_ALLOWED_DEPS = {
    "next",
    "react",
    "react-dom",
    "better-sqlite3",
    "tailwindcss",
    "postcss",
    "autoprefixer",
}


async def run_build_check(code_output: CodeOutput, run_id: str | None = None) -> BuildCheckResult:
    """Run lightweight checks (always) + full build (when enabled). Returns BuildCheckResult."""
    start = time.monotonic()
    issues: list[BuildCheckIssue] = []
    files_checked = 0

    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

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

        # --- package.json: required deps + dep-drift allowlist ---
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
                for extra in sorted(all_deps - _ALLOWED_DEPS):
                    issues.append(BuildCheckIssue(
                        file="package.json",
                        severity="error",
                        message=(
                            f"Dependency '{extra}' is not in the build sandbox. "
                            f"Remove it or extend backend/build_sandbox/package.json + rerun setup_build_sandbox.sh."
                        ),
                        check="dep_drift",
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

        # --- JS syntax checks via `node --check` ---
        for code_file in code_output.files:
            if code_file.language == "javascript":
                files_checked += 1
                file_path = tmp / code_file.path
                js_issues = await _check_js_syntax(code_file.path, file_path)
                issues.extend(js_issues)

        # --- Full build (sandbox-backed, gated by flag) ---
        full_build_attempted = False
        full_build_log: str | None = None

        if settings.enable_full_build_check:
            full_build_attempted = True
            full_build_log, build_issues = await _run_full_build(code_output, run_id or _fallback_run_id())
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


def _fallback_run_id() -> str:
    return f"adhoc-{int(time.monotonic() * 1000)}"


async def _check_js_syntax(rel_path: str, abs_path: Path) -> list[BuildCheckIssue]:
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
        return []

    if proc.returncode == 0:
        return []
    return _parse_node_stderr(rel_path, stderr.decode(errors="replace"))


def _parse_node_stderr(rel_path: str, stderr: str) -> list[BuildCheckIssue]:
    issues: list[BuildCheckIssue] = []
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


def _hardlink_tree(src: Path, dst: Path) -> None:
    """Replicate src into dst.
    - Hardlinks regular files (same inode → fast, no disk duplication).
    - Preserves symlinks AS symlinks (critical for node_modules/.bin/*).
    - Skips '.cache' directories (Next/SWC writes there; sharing pollutes the sandbox).
    Source and destination must be on the same filesystem (caller guarantees this).
    """
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name == ".cache":
            continue
        target = dst / entry.name
        if entry.is_symlink():
            link_target = os.readlink(entry)
            os.symlink(link_target, target)
        elif entry.is_dir():
            _hardlink_tree(entry, target)
        else:
            try:
                os.link(entry, target)
            except OSError:
                shutil.copy2(entry, target)


async def _run_full_build(code_output: CodeOutput, run_id: str) -> tuple[str, list[BuildCheckIssue]]:
    """Run `next build` in a per-run workdir under the pre-seeded sandbox."""
    issues: list[BuildCheckIssue] = []
    sandbox = Path(settings.build_sandbox_dir).resolve()
    sandbox_modules = sandbox / "node_modules"

    if not sandbox_modules.exists():
        return "", [BuildCheckIssue(
            file="build_sandbox",
            severity="error",
            message=(
                f"Build sandbox not found at {sandbox}. "
                f"Run `bash backend/scripts/setup_build_sandbox.sh` to create it, "
                f"or set enable_full_build_check=False to skip this check."
            ),
            check="sandbox_missing",
        )]

    # Workdir lives UNDER the sandbox to guarantee same-filesystem hardlinks.
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", run_id)[:64] or "adhoc"
    workdir = sandbox / "_runs" / safe_id
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)

    log_lines: list[str] = []
    try:
        # Hardlink node_modules
        _hardlink_tree(sandbox_modules, workdir / "node_modules")

        # Provide package.json + next.config.js if the Developer didn't
        provided_paths = {f.path for f in code_output.files}
        if "package.json" not in provided_paths:
            shutil.copy2(sandbox / "package.json", workdir / "package.json")
        if not any(p in provided_paths for p in ("next.config.js", "next.config.mjs")):
            shutil.copy2(sandbox / "next.config.js", workdir / "next.config.js")

        # Write generated source files
        for code_file in code_output.files:
            dest = workdir / code_file.path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(code_file.content, encoding="utf-8")

        # Subprocess env: explicit allowlist only.
        # NEVER spread os.environ here — the Developer agent's JS runs inside
        # `next build` and any var present would be readable via process.env,
        # creating an exfiltration path for ANTHROPIC_API_KEY and other secrets.
        env: dict[str, str] = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(workdir),
            "NODE_ENV": "production",
            "CI": "1",
            "NEXT_TELEMETRY_DISABLED": "1",
        }
        for optional_key in ("TMPDIR", "TEMP", "TMP", "NODE_PATH", "npm_config_cache"):
            value = os.environ.get(optional_key)
            if value is not None:
                env[optional_key] = value
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "next", "build",
                cwd=str(workdir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=settings.full_build_timeout_seconds,
                )
            except asyncio.TimeoutError:
                proc.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                issues.append(BuildCheckIssue(
                    file=code_output.project_name,
                    severity="error",
                    message=f"`next build` timed out after {settings.full_build_timeout_seconds}s.",
                    check="next_build",
                ))
                log_lines.append("$ npx next build")
                log_lines.append("(timeout)")
                return "\n".join(log_lines), issues

            stdout_text = stdout.decode(errors="replace")
            stderr_text = stderr.decode(errors="replace")
            log_lines.append("$ npx next build")
            log_lines.append("--- stdout ---")
            log_lines.append(stdout_text)
            log_lines.append("--- stderr ---")
            log_lines.append(stderr_text)

            if proc.returncode != 0:
                issues.append(BuildCheckIssue(
                    file=code_output.project_name,
                    severity="error",
                    message=f"`next build` failed (exit {proc.returncode}). See build log for details.",
                    check="next_build",
                ))
        except FileNotFoundError:
            issues.append(BuildCheckIssue(
                file=code_output.project_name,
                severity="error",
                message="`npx` not found on PATH. Cannot run full build check.",
                check="next_build",
            ))

    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return "\n".join(log_lines), issues
