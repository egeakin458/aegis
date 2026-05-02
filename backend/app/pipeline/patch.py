"""
Patch application helper.

Merges a CodePatch (partial update from a revision cycle) into a CodeOutput
(the full project state). Produces a new CodeOutput with the patch applied.
"""

from __future__ import annotations

import logging

from app.schemas.agent_outputs import CodeFile, CodeOutput, CodePatch, FeatureImplementation

logger = logging.getLogger(__name__)


def apply_patch(previous: CodeOutput, patch: CodePatch) -> CodeOutput:
    """Apply a CodePatch to a previous CodeOutput and return the merged result.

    Semantics:
    - files_to_replace: overwrite matching paths; insert at end if path is new.
    - files_to_delete: remove files by path; warn and skip if path not found.
    - features_implemented_delta: merged into previous list, deduplicated by feature_id.
    - setup_instructions: updated only when patch.setup_instructions_changed is True.
    """
    # Build a mutable index of current files
    file_index: dict[str, CodeFile] = {f.path: f for f in previous.files}

    # Apply replacements / insertions
    for replacement in patch.files_to_replace:
        if replacement.path in file_index:
            logger.debug("Patch: replacing %s", replacement.path)
        else:
            logger.debug("Patch: inserting new file %s", replacement.path)
        file_index[replacement.path] = replacement

    # Apply deletions
    for path_to_delete in patch.files_to_delete:
        if path_to_delete in file_index:
            del file_index[path_to_delete]
            logger.debug("Patch: deleted %s", path_to_delete)
        else:
            logger.warning("Patch: delete requested for non-existent path '%s' — skipping.", path_to_delete)

    # Merge features_implemented (deduplicate by feature_id, delta wins on conflict)
    existing_by_id: dict[str, FeatureImplementation] = {
        f.feature_id: f for f in previous.features_implemented
    }
    for delta_feature in patch.features_implemented_delta:
        existing_by_id[delta_feature.feature_id] = delta_feature
    merged_features = list(existing_by_id.values())

    # Preserve file insertion order: existing order for survivors, appended for new
    existing_paths = [f.path for f in previous.files]
    ordered_files: list[CodeFile] = []
    for path in existing_paths:
        if path in file_index and path not in [f.path for f in patch.files_to_delete]:
            ordered_files.append(file_index.pop(path))
    # Remaining items in file_index are new files (from files_to_replace with new paths)
    ordered_files.extend(file_index.values())

    setup = (
        patch.new_setup_instructions
        if patch.setup_instructions_changed and patch.new_setup_instructions
        else previous.setup_instructions
    )

    return CodeOutput(
        reasoning=patch.reasoning,
        project_name=previous.project_name,
        files=ordered_files,
        setup_instructions=setup,
        features_implemented=merged_features,
        known_limitations=previous.known_limitations,
    )
