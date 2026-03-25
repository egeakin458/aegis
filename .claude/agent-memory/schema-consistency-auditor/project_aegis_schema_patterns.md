---
name: Aegis Schema Patterns and Conventions
description: Field naming conventions, context key mappings, and structural patterns observed in the Aegis schema layer as of the first audit (2026-03-21).
type: project
---

Key schema facts observed in the first full audit (Phase 1, 2026-03-21):

**Pipeline data flow:**
CustomerConfig → RA → FinalizedConfig → SA → TechnicalDesign → Dev → CodeOutput → QA → QAReview

**Context dict key conventions (to be enforced in PipelineRunner):**
- SA receives: `{"finalized_config": FinalizedConfig}`
- Dev receives: `{"finalized_config": FinalizedConfig, "technical_design": TechnicalDesign}`
- QA receives: `{"finalized_config": FinalizedConfig, "technical_design": TechnicalDesign, "code_output": CodeOutput}`

**Why:** No PipelineRunner exists yet; these key names are not yet formally defined anywhere in code. When implementing, use snake_case matching schema class names.

**How to apply:** When auditing PipelineRunner once implemented, verify exact context key names match what agents read via `context["key"]`.

**FinalizedConfig wraps CustomerConfig:** The RA output is `FinalizedConfig` which has a `config: CustomerConfig` field — SA must access nested fields as `finalized_config.config.business_context`, not directly.

**IssueSeverity enum not re-exported:** `IssueSeverity` from `agent_outputs.py` is imported nowhere outside that file and is not in `__init__.py` — a known gap as of first audit.

**Enum export gaps in __init__.py:** The following enums defined in schemas are NOT re-exported from `app/schemas/__init__.py`:
- From `customer_config.py`: IndustryType, BusinessSize, UserType, AccessScope, DesignStyle, MobileSupport, DataVolume
- From `agent_outputs.py`: IssueSeverity
- From `evaluation.py`: ComplexityTier

**BaseAgent emits VALIDATION_PASSED instead of AGENT_COMPLETE:** On success, base.py emits EventType.VALIDATION_PASSED. EventType.AGENT_COMPLETE exists in the enum but is never emitted. This is a behavioral gap, not a compile error.

**DesignPreferences default_factory pattern:** `DesignPreferences()` with no args is valid because all its fields have defaults (colors=None, logo=None, references=[], style=NO_PREFERENCE). Same for TechnicalRequirements and ProjectMeta.
