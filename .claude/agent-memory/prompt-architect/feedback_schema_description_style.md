---
name: Schema description style for Aegis prompts
description: How to describe Pydantic schemas in system prompts — hierarchical natural language with exact field names and enum values
type: feedback
---

Describe output schemas as hierarchical natural language with exact field names, types, and valid enum values. For each field: name in quotes, type, purpose, and constraints. For nested objects: indent or describe as "object with:" followed by field list. For enums: list all valid string values in quotes.

**Why:** Pasting raw Pydantic code into prompts causes LLMs to sometimes output Python-style syntax instead of valid JSON. Natural language descriptions with exact field names produce cleaner JSON on the first attempt, reducing retry rates.

**How to apply:** Every Aegis agent prompt's OUTPUT FORMAT section should follow this pattern. Never use Field(...), Optional[], list[], or other Pydantic syntax. Use "string or null", "list of X objects", "boolean", "integer, 1 or higher".
