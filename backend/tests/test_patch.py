"""
Tests for app/pipeline/patch.py — apply_patch semantics.

Coverage:
- Replace existing file → content updated, others untouched
- Add new file via replace → file added at end
- Delete existing file → file removed
- Delete non-existent file → warn-logged, no error
- Empty patch → CodeOutput unchanged
- Multiple replace + delete in one patch → all applied
- features_implemented dedup by feature_id (delta wins on conflict)
- setup_instructions updated only when setup_instructions_changed=True
"""

from __future__ import annotations

import logging

import pytest

from app.pipeline.patch import apply_patch
from app.schemas.agent_outputs import (
    CodeFile,
    CodeOutput,
    CodePatch,
    FeatureImplementation,
)


def _file(path: str, content: str = "// content", language: str = "javascript") -> CodeFile:
    return CodeFile(path=path, content=content, language=language, description=path)


def _feature(feature_id: str, description: str) -> FeatureImplementation:
    return FeatureImplementation(feature_id=feature_id, description=description)


def _base_output(files: list[CodeFile] | None = None, features: list[FeatureImplementation] | None = None) -> CodeOutput:
    return CodeOutput(
        reasoning="Initial build.",
        project_name="test-app",
        files=files or [_file("app/page.js"), _file("app/layout.js"), _file("package.json", language="json")],
        setup_instructions="npm install && npm run dev",
        features_implemented=features or [_feature("feat_a_111111", "Feature A")],
        known_limitations=[],
    )


def _empty_patch() -> CodePatch:
    return CodePatch(reasoning="No changes.")


class TestReplaceFile:
    def test_existing_file_content_updated(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Fix page.",
            files_to_replace=[_file("app/page.js", content="// fixed")],
        )
        result = apply_patch(base, patch)
        page = next(f for f in result.files if f.path == "app/page.js")
        assert page.content == "// fixed"

    def test_other_files_unchanged(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Fix page.",
            files_to_replace=[_file("app/page.js", content="// fixed")],
        )
        result = apply_patch(base, patch)
        layout = next(f for f in result.files if f.path == "app/layout.js")
        assert layout.content == "// content"

    def test_file_count_unchanged_on_replace(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Fix.",
            files_to_replace=[_file("app/page.js", content="// fixed")],
        )
        result = apply_patch(base, patch)
        assert len(result.files) == len(base.files)

    def test_new_file_path_added(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Add new file.",
            files_to_replace=[_file("app/new-page.js", content="// new")],
        )
        result = apply_patch(base, patch)
        paths = [f.path for f in result.files]
        assert "app/new-page.js" in paths
        assert len(result.files) == len(base.files) + 1


class TestDeleteFile:
    def test_existing_file_removed(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Remove.",
            files_to_delete=["app/layout.js"],
        )
        result = apply_patch(base, patch)
        paths = [f.path for f in result.files]
        assert "app/layout.js" not in paths

    def test_other_files_still_present(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Remove.",
            files_to_delete=["app/layout.js"],
        )
        result = apply_patch(base, patch)
        paths = [f.path for f in result.files]
        assert "app/page.js" in paths

    def test_file_count_decremented(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Remove.",
            files_to_delete=["app/layout.js"],
        )
        result = apply_patch(base, patch)
        assert len(result.files) == len(base.files) - 1

    def test_delete_nonexistent_file_no_error(self, caplog):
        base = _base_output()
        patch = CodePatch(
            reasoning="Delete ghost.",
            files_to_delete=["app/ghost.js"],
        )
        with caplog.at_level(logging.WARNING):
            result = apply_patch(base, patch)
        assert len(result.files) == len(base.files)
        assert "ghost.js" in caplog.text


class TestEmptyPatch:
    def test_empty_patch_output_unchanged(self):
        base = _base_output()
        patch = _empty_patch()
        result = apply_patch(base, patch)
        assert len(result.files) == len(base.files)
        assert result.setup_instructions == base.setup_instructions
        assert result.project_name == base.project_name


class TestMultipleChanges:
    def test_replace_and_delete_in_one_patch(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Multi.",
            files_to_replace=[_file("app/page.js", content="// updated")],
            files_to_delete=["app/layout.js"],
        )
        result = apply_patch(base, patch)
        paths = [f.path for f in result.files]
        assert "app/layout.js" not in paths
        assert "app/page.js" in paths
        page = next(f for f in result.files if f.path == "app/page.js")
        assert page.content == "// updated"


class TestFeatureDedup:
    def test_delta_feature_added(self):
        base = _base_output(features=[_feature("feat_a_111111", "Feature A")])
        patch = CodePatch(
            reasoning="Add feature B.",
            features_implemented_delta=[_feature("feat_b_222222", "Feature B")],
        )
        result = apply_patch(base, patch)
        ids = {f.feature_id for f in result.features_implemented}
        assert "feat_a_111111" in ids
        assert "feat_b_222222" in ids

    def test_delta_feature_overwrites_existing_on_conflict(self):
        base = _base_output(features=[_feature("feat_a_111111", "Feature A (old)")])
        patch = CodePatch(
            reasoning="Update feature A.",
            features_implemented_delta=[_feature("feat_a_111111", "Feature A (updated)")],
        )
        result = apply_patch(base, patch)
        feature_a = next(f for f in result.features_implemented if f.feature_id == "feat_a_111111")
        assert feature_a.description == "Feature A (updated)"
        assert len(result.features_implemented) == 1

    def test_empty_delta_preserves_existing(self):
        base = _base_output(features=[_feature("feat_a_111111", "Feature A")])
        patch = _empty_patch()
        result = apply_patch(base, patch)
        assert len(result.features_implemented) == 1


class TestSetupInstructions:
    def test_setup_unchanged_when_flag_false(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="No setup change.",
            setup_instructions_changed=False,
            new_setup_instructions="npm run new",
        )
        result = apply_patch(base, patch)
        assert result.setup_instructions == base.setup_instructions

    def test_setup_updated_when_flag_true(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Updated setup.",
            setup_instructions_changed=True,
            new_setup_instructions="npm run new && npm start",
        )
        result = apply_patch(base, patch)
        assert result.setup_instructions == "npm run new && npm start"

    def test_setup_unchanged_when_flag_true_but_no_new_instructions(self):
        base = _base_output()
        patch = CodePatch(
            reasoning="Flag set but no value.",
            setup_instructions_changed=True,
            new_setup_instructions=None,
        )
        result = apply_patch(base, patch)
        assert result.setup_instructions == base.setup_instructions
