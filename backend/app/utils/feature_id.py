"""Utility for generating stable, human-readable feature identifiers."""

from __future__ import annotations

import re
import uuid


def slug_feature_id(description: str) -> str:
    """
    Generate a stable feature ID from a description string.

    Format: feat_<kebab-slug-truncated-to-32>_<6-char-uuid>
    Example: feat_menu-display-with-category-filte_a4f2c1
    """
    slug = description.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    slug = slug[:32].rstrip("-")
    suffix = uuid.uuid4().hex[:6]
    return f"feat_{slug}_{suffix}"
