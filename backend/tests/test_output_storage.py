"""
Tests for app/pipeline/output_storage.py.

Coverage:
  1. Creates correct directory structure under output_dir/run_id/
  2. Writes file content exactly as provided
  3. Creates valid manifest.json with all required fields
  4. Handles nested paths correctly (e.g. app/api/menu/route.js)
  5. Rejects unsafe paths with a leading '/' — raises ValueError
  6. Rejects unsafe paths containing '..' — raises ValueError
  7. Returns the output directory path
  8. Multiple files all written to disk
  9. manifest.json contains correct file metadata for each file
 10. manifest.json created_at field is a valid ISO-8601 datetime
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pipeline.output_storage import save_output
from app.schemas.agent_outputs import CodeFile, CodeOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def use_tmp_dir(tmp_path, monkeypatch):
    """Redirect output_dir to a temporary directory for every test."""
    monkeypatch.setattr("app.pipeline.output_storage.settings.output_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def sample_run_id() -> str:
    return "run-00000000-0000-0000-0000-000000000042"


@pytest.fixture
def single_file_code_output() -> CodeOutput:
    """CodeOutput with one flat-path file."""
    return CodeOutput(
        reasoning="Simple implementation",
        project_name="test-app",
        files=[
            CodeFile(
                path="package.json",
                content='{"name": "test-app", "version": "1.0.0"}',
                language="json",
                description="Package manifest",
            )
        ],
        setup_instructions="npm install && npm run dev",
        features_implemented=["Feature A"],
    )


@pytest.fixture
def multi_file_code_output() -> CodeOutput:
    """CodeOutput with several files including nested paths."""
    return CodeOutput(
        reasoning="Full project implementation",
        project_name="cafe-ordering",
        files=[
            CodeFile(
                path="package.json",
                content='{"name": "cafe-ordering"}',
                language="json",
                description="Package manifest",
            ),
            CodeFile(
                path="app/page.js",
                content="export default function Home() { return <div>Home</div>; }",
                language="javascript",
                description="Home page",
            ),
            CodeFile(
                path="app/api/orders/route.js",
                content="export async function GET() { return Response.json([]); }",
                language="javascript",
                description="Orders API route",
            ),
            CodeFile(
                path="lib/db.js",
                content="const Database = require('better-sqlite3'); module.exports = new Database('app.db');",
                language="javascript",
                description="Database connection",
            ),
        ],
        setup_instructions="npm install && npm run dev",
        features_implemented=["Order listing", "Database setup"],
        known_limitations=["No authentication"],
    )


# ---------------------------------------------------------------------------
# 1. Directory structure
# ---------------------------------------------------------------------------


class TestDirectoryStructure:
    @pytest.mark.asyncio
    async def test_save_output_creates_run_id_subdirectory(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        assert (tmp_path / sample_run_id).is_dir()

    @pytest.mark.asyncio
    async def test_save_output_returns_output_directory_path(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        result = await save_output(sample_run_id, single_file_code_output)
        assert result == tmp_path / sample_run_id

    @pytest.mark.asyncio
    async def test_save_output_returned_path_is_a_directory(
        self, sample_run_id, single_file_code_output
    ):
        result = await save_output(sample_run_id, single_file_code_output)
        assert result.is_dir()

    @pytest.mark.asyncio
    async def test_save_output_creates_nested_parent_directories(
        self, tmp_path, sample_run_id, multi_file_code_output
    ):
        await save_output(sample_run_id, multi_file_code_output)
        assert (tmp_path / sample_run_id / "app" / "api" / "orders").is_dir()


# ---------------------------------------------------------------------------
# 2. File content
# ---------------------------------------------------------------------------


class TestFileContent:
    @pytest.mark.asyncio
    async def test_save_output_writes_flat_file_content(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        file_path = tmp_path / sample_run_id / "package.json"
        assert file_path.exists()
        content = file_path.read_text(encoding="utf-8")
        assert content == '{"name": "test-app", "version": "1.0.0"}'

    @pytest.mark.asyncio
    async def test_save_output_writes_nested_file_content(
        self, tmp_path, sample_run_id, multi_file_code_output
    ):
        await save_output(sample_run_id, multi_file_code_output)
        file_path = tmp_path / sample_run_id / "app" / "api" / "orders" / "route.js"
        assert file_path.exists()
        content = file_path.read_text(encoding="utf-8")
        assert "GET" in content

    @pytest.mark.asyncio
    async def test_save_output_preserves_exact_content_including_newlines(
        self, tmp_path, sample_run_id
    ):
        multiline_content = "line one\nline two\nline three\n"
        code_output = CodeOutput(
            reasoning="Test",
            project_name="test",
            files=[
                CodeFile(
                    path="file.txt",
                    content=multiline_content,
                    language="markdown",
                    description="Text file",
                )
            ],
            setup_instructions="none",
            features_implemented=["feature"],
        )
        await save_output(sample_run_id, code_output)
        written = (tmp_path / sample_run_id / "file.txt").read_text(encoding="utf-8")
        assert written == multiline_content

    @pytest.mark.asyncio
    async def test_save_output_writes_all_files(
        self, tmp_path, sample_run_id, multi_file_code_output
    ):
        await save_output(sample_run_id, multi_file_code_output)
        expected_paths = [
            tmp_path / sample_run_id / "package.json",
            tmp_path / sample_run_id / "app" / "page.js",
            tmp_path / sample_run_id / "app" / "api" / "orders" / "route.js",
            tmp_path / sample_run_id / "lib" / "db.js",
        ]
        for p in expected_paths:
            assert p.exists(), f"Expected file not found: {p}"

    @pytest.mark.asyncio
    async def test_save_output_handles_unicode_content(
        self, tmp_path, sample_run_id
    ):
        unicode_content = "// Türkçe yorum: merhaba dünya\nconst x = '价格';\n"
        code_output = CodeOutput(
            reasoning="Unicode test",
            project_name="unicode-app",
            files=[
                CodeFile(
                    path="index.js",
                    content=unicode_content,
                    language="javascript",
                    description="File with unicode",
                )
            ],
            setup_instructions="none",
            features_implemented=["unicode support"],
        )
        await save_output(sample_run_id, code_output)
        written = (tmp_path / sample_run_id / "index.js").read_text(encoding="utf-8")
        assert written == unicode_content


# ---------------------------------------------------------------------------
# 3. Manifest creation
# ---------------------------------------------------------------------------


class TestManifestCreation:
    @pytest.mark.asyncio
    async def test_save_output_creates_manifest_json(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest_path = tmp_path / sample_run_id / "manifest.json"
        assert manifest_path.exists()

    @pytest.mark.asyncio
    async def test_manifest_contains_run_id(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["run_id"] == sample_run_id

    @pytest.mark.asyncio
    async def test_manifest_contains_project_name(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["project_name"] == "test-app"

    @pytest.mark.asyncio
    async def test_manifest_contains_setup_instructions(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["setup_instructions"] == "npm install && npm run dev"

    @pytest.mark.asyncio
    async def test_manifest_contains_features_implemented(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["features_implemented"] == ["Feature A"]

    @pytest.mark.asyncio
    async def test_manifest_contains_files_list(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert "files" in manifest
        assert len(manifest["files"]) == 1

    @pytest.mark.asyncio
    async def test_manifest_file_entry_contains_path(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["files"][0]["path"] == "package.json"

    @pytest.mark.asyncio
    async def test_manifest_file_entry_contains_language(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["files"][0]["language"] == "json"

    @pytest.mark.asyncio
    async def test_manifest_file_entry_contains_description(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["files"][0]["description"] == "Package manifest"

    @pytest.mark.asyncio
    async def test_manifest_created_at_is_valid_iso8601(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        from datetime import datetime

        parsed = datetime.fromisoformat(manifest["created_at"])
        assert parsed is not None

    @pytest.mark.asyncio
    async def test_manifest_file_list_does_not_include_manifest_itself(
        self, tmp_path, sample_run_id, single_file_code_output
    ):
        await save_output(sample_run_id, single_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        file_paths = [f["path"] for f in manifest["files"]]
        assert "manifest.json" not in file_paths

    @pytest.mark.asyncio
    async def test_manifest_files_list_length_matches_code_output_files(
        self, tmp_path, sample_run_id, multi_file_code_output
    ):
        await save_output(sample_run_id, multi_file_code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert len(manifest["files"]) == len(multi_file_code_output.files)


# ---------------------------------------------------------------------------
# 4. Nested paths
# ---------------------------------------------------------------------------


class TestNestedPaths:
    @pytest.mark.asyncio
    async def test_nested_path_file_is_created(
        self, tmp_path, sample_run_id
    ):
        code_output = CodeOutput(
            reasoning="Nested test",
            project_name="nested-app",
            files=[
                CodeFile(
                    path="app/api/menu/route.js",
                    content="export async function GET() {}",
                    language="javascript",
                    description="Menu API route",
                )
            ],
            setup_instructions="npm install",
            features_implemented=["menu api"],
        )
        await save_output(sample_run_id, code_output)
        assert (tmp_path / sample_run_id / "app" / "api" / "menu" / "route.js").exists()

    @pytest.mark.asyncio
    async def test_deeply_nested_path_creates_all_parent_dirs(
        self, tmp_path, sample_run_id
    ):
        code_output = CodeOutput(
            reasoning="Deep nesting test",
            project_name="deep-app",
            files=[
                CodeFile(
                    path="a/b/c/d/e/deep.js",
                    content="const x = 1;",
                    language="javascript",
                    description="Deeply nested file",
                )
            ],
            setup_instructions="none",
            features_implemented=["deep nesting"],
        )
        await save_output(sample_run_id, code_output)
        assert (tmp_path / sample_run_id / "a" / "b" / "c" / "d" / "e" / "deep.js").exists()

    @pytest.mark.asyncio
    async def test_nested_path_appears_correctly_in_manifest(
        self, tmp_path, sample_run_id
    ):
        code_output = CodeOutput(
            reasoning="Manifest path test",
            project_name="path-app",
            files=[
                CodeFile(
                    path="app/api/menu/route.js",
                    content="",
                    language="javascript",
                    description="Route",
                )
            ],
            setup_instructions="none",
            features_implemented=["routing"],
        )
        await save_output(sample_run_id, code_output)
        manifest = json.loads(
            (tmp_path / sample_run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["files"][0]["path"] == "app/api/menu/route.js"


# ---------------------------------------------------------------------------
# 5. Unsafe path rejection — leading slash
# ---------------------------------------------------------------------------


class TestUnsafePathAbsolute:
    @pytest.mark.asyncio
    async def test_absolute_path_raises_value_error(self, sample_run_id):
        code_output = CodeOutput(
            reasoning="Security test",
            project_name="bad-app",
            files=[
                CodeFile(
                    path="/etc/passwd",
                    content="evil content",
                    language="markdown",
                    description="Unsafe file",
                )
            ],
            setup_instructions="none",
            features_implemented=["security bypass"],
        )
        with pytest.raises(ValueError, match="Unsafe file path"):
            await save_output(sample_run_id, code_output)

    @pytest.mark.asyncio
    async def test_absolute_path_raises_value_error_for_slash_app(
        self, sample_run_id
    ):
        code_output = CodeOutput(
            reasoning="Security test",
            project_name="bad-app",
            files=[
                CodeFile(
                    path="/app/page.js",
                    content="const x = 1;",
                    language="javascript",
                    description="Absolute path that looks like app route",
                )
            ],
            setup_instructions="none",
            features_implemented=["home page"],
        )
        with pytest.raises(ValueError, match="Unsafe file path"):
            await save_output(sample_run_id, code_output)

    @pytest.mark.asyncio
    async def test_absolute_path_does_not_write_any_file(
        self, tmp_path, sample_run_id
    ):
        code_output = CodeOutput(
            reasoning="Security test",
            project_name="bad-app",
            files=[
                CodeFile(
                    path="/tmp/evil.js",
                    content="evil",
                    language="javascript",
                    description="Unsafe",
                )
            ],
            setup_instructions="none",
            features_implemented=["none"],
        )
        with pytest.raises(ValueError):
            await save_output(sample_run_id, code_output)
        # The output subdirectory may have been created, but the evil file must not exist
        assert not (tmp_path / "tmp" / "evil.js").exists()


# ---------------------------------------------------------------------------
# 6. Unsafe path rejection — directory traversal with ..
# ---------------------------------------------------------------------------


class TestUnsafePathTraversal:
    @pytest.mark.asyncio
    async def test_dotdot_path_raises_value_error(self, sample_run_id):
        code_output = CodeOutput(
            reasoning="Traversal test",
            project_name="bad-app",
            files=[
                CodeFile(
                    path="../outside/evil.js",
                    content="evil",
                    language="javascript",
                    description="Traversal attempt",
                )
            ],
            setup_instructions="none",
            features_implemented=["traversal"],
        )
        with pytest.raises(ValueError, match="Unsafe file path"):
            await save_output(sample_run_id, code_output)

    @pytest.mark.asyncio
    async def test_embedded_dotdot_path_raises_value_error(self, sample_run_id):
        code_output = CodeOutput(
            reasoning="Embedded traversal test",
            project_name="bad-app",
            files=[
                CodeFile(
                    path="app/../../../etc/passwd",
                    content="evil",
                    language="markdown",
                    description="Embedded traversal",
                )
            ],
            setup_instructions="none",
            features_implemented=["traversal"],
        )
        with pytest.raises(ValueError, match="Unsafe file path"):
            await save_output(sample_run_id, code_output)

    @pytest.mark.asyncio
    async def test_dotdot_in_filename_raises_value_error(self, sample_run_id):
        code_output = CodeOutput(
            reasoning="Dotdot in name",
            project_name="bad-app",
            files=[
                CodeFile(
                    path="app/..bad/file.js",
                    content="const x = 1;",
                    language="javascript",
                    description="Has dotdot in path segment",
                )
            ],
            setup_instructions="none",
            features_implemented=["none"],
        )
        with pytest.raises(ValueError, match="Unsafe file path"):
            await save_output(sample_run_id, code_output)

    @pytest.mark.asyncio
    async def test_safe_path_with_dotdot_in_content_does_not_raise(
        self, tmp_path, sample_run_id
    ):
        # The content can contain '..', only the path is checked
        code_output = CodeOutput(
            reasoning="Safe path, dotdot content",
            project_name="safe-app",
            files=[
                CodeFile(
                    path="app/page.js",
                    content="const rel = '../assets/logo.png';",
                    language="javascript",
                    description="File with relative path in content",
                )
            ],
            setup_instructions="none",
            features_implemented=["logo display"],
        )
        # Should not raise
        await save_output(sample_run_id, code_output)
        assert (tmp_path / sample_run_id / "app" / "page.js").exists()
