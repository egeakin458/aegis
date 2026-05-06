"""
Tests for app/pipeline/build_checker.py.

Covers:
- JS syntax errors detected via node --check (or skipped gracefully if node absent)
- Invalid JSON caught with line/column
- Missing required files flagged
- Valid minimal Next.js structure passes
- package.json dependency check
- Full build path scaffolded (mocked subprocess)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline.build_checker import run_build_check, _parse_node_stderr
from app.schemas.agent_outputs import CodeFile, CodeOutput, FeatureImplementation


def _make_code_output(files: list[dict]) -> CodeOutput:
    return CodeOutput(
        reasoning="Test output.",
        project_name="test-app",
        files=[CodeFile(**f) for f in files],
        setup_instructions="npm install && npm run dev",
        features_implemented=[
            FeatureImplementation(
                feature_id="feat_test_abc123",
                description="Test feature",
                implementation_notes=None,
            )
        ],
        known_limitations=[],
    )


def _minimal_valid_files() -> list[dict]:
    """Minimal set of files that passes all structural checks."""
    pkg = {
        "name": "test-app",
        "dependencies": {
            "next": "14.0.0",
            "react": "18.0.0",
            "better-sqlite3": "9.0.0",
            "tailwindcss": "3.0.0",
        },
    }
    return [
        {
            "path": "app/layout.js",
            "content": "export default function RootLayout({ children }) { return <html><body>{children}</body></html>; }",
            "language": "javascript",
            "description": "Root layout",
        },
        {
            "path": "app/page.js",
            "content": "export default function Home() { return <div>Home</div>; }",
            "language": "javascript",
            "description": "Home page",
        },
        {
            "path": "package.json",
            "content": json.dumps(pkg),
            "language": "json",
            "description": "Package manifest",
        },
    ]


class TestMissingRequiredFiles:
    @pytest.mark.asyncio
    async def test_missing_layout_flagged(self):
        files = [f for f in _minimal_valid_files() if f["path"] != "app/layout.js"]
        result = await run_build_check(_make_code_output(files))
        paths = [i.file for i in result.issues]
        assert "app/layout.js" in paths

    @pytest.mark.asyncio
    async def test_missing_page_flagged(self):
        files = [f for f in _minimal_valid_files() if f["path"] != "app/page.js"]
        result = await run_build_check(_make_code_output(files))
        paths = [i.file for i in result.issues]
        assert "app/page.js" in paths

    @pytest.mark.asyncio
    async def test_missing_package_json_flagged(self):
        files = [f for f in _minimal_valid_files() if f["path"] != "package.json"]
        result = await run_build_check(_make_code_output(files))
        paths = [i.file for i in result.issues]
        assert "package.json" in paths

    @pytest.mark.asyncio
    async def test_all_required_files_present_no_missing_file_issue(self):
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(_minimal_valid_files()))
        missing = [i for i in result.issues if i.check == "missing_required_file"]
        assert missing == []


class TestPackageJsonCheck:
    @pytest.mark.asyncio
    async def test_invalid_json_in_package_json(self):
        files = _minimal_valid_files()
        for f in files:
            if f["path"] == "package.json":
                f["content"] = '{"name": "test", INVALID}'
        result = await run_build_check(_make_code_output(files))
        json_issues = [i for i in result.issues if i.check == "json_parse" and i.file == "package.json"]
        assert len(json_issues) >= 1
        assert json_issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_missing_dependency_flagged(self):
        pkg = {"name": "test-app", "dependencies": {"next": "14.0.0", "react": "18.0.0"}}
        files = _minimal_valid_files()
        for f in files:
            if f["path"] == "package.json":
                f["content"] = json.dumps(pkg)
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(files))
        dep_issues = [i for i in result.issues if "better-sqlite3" in i.message or "tailwindcss" in i.message]
        assert len(dep_issues) >= 1


class TestJsonFileCheck:
    @pytest.mark.asyncio
    async def test_invalid_json_file_flagged(self):
        files = _minimal_valid_files() + [
            {
                "path": "data/config.json",
                "content": '{"key": INVALID}',
                "language": "json",
                "description": "Config file",
            }
        ]
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(files))
        json_issues = [i for i in result.issues if i.file == "data/config.json"]
        assert len(json_issues) == 1
        assert json_issues[0].check == "json_parse"

    @pytest.mark.asyncio
    async def test_valid_json_file_passes(self):
        files = _minimal_valid_files() + [
            {
                "path": "data/config.json",
                "content": '{"key": "value"}',
                "language": "json",
                "description": "Config file",
            }
        ]
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(files))
        json_issues = [i for i in result.issues if i.file == "data/config.json"]
        assert json_issues == []


class TestParseNodeStderr:
    def test_extracts_line_number(self):
        stderr = "/tmp/file.js:12\n^\n\nSyntaxError: Unexpected token"
        issues = _parse_node_stderr("app/page.js", stderr)
        assert len(issues) == 1
        assert issues[0].line == 12
        assert "SyntaxError" in issues[0].message

    def test_no_line_number_fallback(self):
        stderr = "SyntaxError: Something broke"
        issues = _parse_node_stderr("app/page.js", stderr)
        assert len(issues) == 1
        assert issues[0].line is None
        assert issues[0].check == "syntax_js"


class TestValidMinimalApp:
    @pytest.mark.asyncio
    async def test_valid_app_passes(self):
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(_minimal_valid_files()))
        assert result.passed is True
        assert result.issues == []

    @pytest.mark.asyncio
    async def test_files_checked_count(self):
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(_minimal_valid_files()))
        # package.json + 2 js files (if any non-json non-package files counted)
        # package.json is files_checked=1 + js files counted as files_checked too
        assert result.files_checked >= 1


class TestFullBuildPath:
    @pytest.mark.asyncio
    async def test_full_build_not_attempted_when_disabled(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.enable_full_build_check", False)
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(_minimal_valid_files()))
        assert result.full_build_attempted is False

    @pytest.mark.asyncio
    async def test_full_build_attempted_when_enabled(self, tmp_path, monkeypatch):
        # Create a minimal fake sandbox so _run_full_build sees node_modules and proceeds.
        fake_sandbox = tmp_path / "sandbox"
        (fake_sandbox / "node_modules").mkdir(parents=True)
        (fake_sandbox / "package.json").write_text("{}")
        (fake_sandbox / "next.config.js").write_text("module.exports = {};")
        monkeypatch.setattr("app.config.settings.build_sandbox_dir", str(fake_sandbox))
        monkeypatch.setattr("app.config.settings.enable_full_build_check", True)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Build OK\n", b""))

        async def _fake_exec(*args, **kwargs):
            # node --check (lightweight) returns success; npx next build returns success.
            return mock_proc

        with (
            patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])),
            patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_fake_exec)),
        ):
            result = await run_build_check(
                _make_code_output(_minimal_valid_files()),
                run_id="test-run-1",
            )
        assert result.full_build_attempted is True

    @pytest.mark.asyncio
    async def test_sandbox_missing_fails_loud(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.settings.build_sandbox_dir", str(tmp_path / "no-sandbox"))
        monkeypatch.setattr("app.config.settings.enable_full_build_check", True)

        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(
                _make_code_output(_minimal_valid_files()),
                run_id="test-run-2",
            )
        sandbox_issues = [i for i in result.issues if i.check == "sandbox_missing"]
        assert len(sandbox_issues) == 1
        assert "setup_build_sandbox.sh" in sandbox_issues[0].message


class TestDepDrift:
    @pytest.mark.asyncio
    async def test_extra_dep_flagged(self):
        files = _minimal_valid_files()
        for f in files:
            if f["path"] == "package.json":
                pkg = json.loads(f["content"])
                pkg["dependencies"]["lodash"] = "4.17.0"  # NOT in allowlist
                f["content"] = json.dumps(pkg)
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(files))
        drift = [i for i in result.issues if i.check == "dep_drift"]
        assert len(drift) == 1
        assert "lodash" in drift[0].message

    @pytest.mark.asyncio
    async def test_only_allowed_deps_no_drift(self):
        with patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])):
            result = await run_build_check(_make_code_output(_minimal_valid_files()))
        drift = [i for i in result.issues if i.check == "dep_drift"]
        assert drift == []


class TestHardlinkTree:
    def test_skips_cache_and_preserves_symlinks(self, tmp_path):
        from app.pipeline.build_checker import _hardlink_tree
        src = tmp_path / "src"
        src.mkdir()
        (src / "regular.js").write_text("hello")
        (src / ".cache").mkdir()
        (src / ".cache" / "ignore.me").write_text("nope")
        (src / "subdir").mkdir()
        (src / "subdir" / "real.js").write_text("real")
        (src / "alias.js").symlink_to("subdir/real.js")

        dst = tmp_path / "dst"
        _hardlink_tree(src, dst)

        assert (dst / "regular.js").read_text() == "hello"
        assert not (dst / ".cache").exists()
        assert (dst / "alias.js").is_symlink()
        assert (dst / "subdir" / "real.js").read_text() == "real"
        # Hardlink check: same inode as source for a regular file
        assert (dst / "regular.js").stat().st_ino == (src / "regular.js").stat().st_ino
