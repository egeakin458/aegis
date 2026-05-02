"""
Tests for app/utils/feature_id.py.

Coverage:
  1. Format — output starts with 'feat_', ends with 6-char hex suffix
  2. Slugification — lowercase, ASCII, non-alphanumeric → dash, collapse repeats
  3. Truncation — slug portion capped at 32 chars
  4. Uniqueness — two calls with identical input produce different IDs (collision suffix)
  5. Edge cases — empty string, all-special chars, leading/trailing dashes
"""

from __future__ import annotations

import re

import pytest

from app.utils.feature_id import slug_feature_id


class TestSlugFeatureId:
    def test_output_starts_with_feat_prefix(self):
        result = slug_feature_id("Order listing")
        assert result.startswith("feat_")

    def test_output_ends_with_6_char_hex_suffix(self):
        result = slug_feature_id("Order listing")
        suffix = result.split("_")[-1]
        assert len(suffix) == 6
        assert re.fullmatch(r"[0-9a-f]{6}", suffix)

    def test_slug_is_lowercase(self):
        result = slug_feature_id("UPPERCASE FEATURE")
        slug_part = result[len("feat_"):-7]
        assert slug_part == slug_part.lower()

    def test_spaces_become_dashes(self):
        result = slug_feature_id("order listing page")
        assert "order-listing-page" in result

    def test_special_chars_become_dashes(self):
        result = slug_feature_id("menu/display & filter!")
        slug_part = result[len("feat_"):-7]
        assert re.fullmatch(r"[a-z0-9\-]+", slug_part)

    def test_consecutive_special_chars_collapse_to_single_dash(self):
        result = slug_feature_id("a -- b")
        assert "--" not in result

    def test_slug_portion_max_32_chars(self):
        long_desc = "a" * 100
        result = slug_feature_id(long_desc)
        slug_part = result[len("feat_"):-7]
        assert len(slug_part) <= 32

    def test_no_leading_or_trailing_dashes_in_slug(self):
        result = slug_feature_id("!!!feature!!!")
        slug_part = result[len("feat_"):-7]
        assert not slug_part.startswith("-")
        assert not slug_part.endswith("-")

    def test_two_identical_descriptions_produce_different_ids(self):
        id1 = slug_feature_id("Same feature")
        id2 = slug_feature_id("Same feature")
        assert id1 != id2

    def test_empty_string_produces_valid_id(self):
        result = slug_feature_id("")
        assert result.startswith("feat_")
        parts = result.split("_")
        assert len(parts) >= 2

    def test_unicode_chars_removed(self):
        result = slug_feature_id("Türkçe özellik")
        slug_part = result[len("feat_"):-7]
        assert re.fullmatch(r"[a-z0-9\-]*", slug_part)
