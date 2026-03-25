"""
Output storage for generated code projects.

Writes CodeOutput files to disk under outputs/{run_id}/ and
creates a manifest.json with project metadata.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.schemas.agent_outputs import CodeOutput

logger = logging.getLogger(__name__)


def _sanitize_path(file_path: str, base_dir: Path) -> Path:
    """Reject paths that escape the base directory."""
    if file_path.startswith("/") or ".." in file_path:
        raise ValueError(f"Unsafe file path: {file_path}")
    resolved = (base_dir / file_path).resolve()
    if not str(resolved).startswith(str(base_dir.resolve())):
        raise ValueError(f"Path escapes output directory: {file_path}")
    return resolved


async def save_output(run_id: str, code_output: CodeOutput) -> Path:
    """
    Write all code files to disk and create a manifest.

    Returns the output directory path.
    """
    output_dir = Path(settings.output_dir) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    for code_file in code_output.files:
        file_path = _sanitize_path(code_file.path, output_dir)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code_file.content, encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "project_name": code_output.project_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "setup_instructions": code_output.setup_instructions,
        "features_implemented": code_output.features_implemented,
        "files": [
            {
                "path": f.path,
                "language": f.language,
                "description": f.description,
            }
            for f in code_output.files
        ],
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info(
        "Saved %d files to %s", len(code_output.files), output_dir
    )
    return output_dir
