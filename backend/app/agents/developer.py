"""
Developer agent.

The third agent in the Aegis pipeline. Receives CustomerConfigV2 (DDC) and
TechnicalDesign, and produces CodeOutput — a complete set of code files
forming a runnable project.

Each FeatureImplementation.feature_id must equal the originating
UseCase.id from the DDC.
"""

from __future__ import annotations

import json
from typing import Any, Type

from pydantic import BaseModel

from app.schemas.agent_outputs import CodeOutput, CodePatch
from app.schemas.pipeline_events import AgentName

from .base import BaseAgent

# ---------------------------------------------------------------------------
# DDC system prompt
# ---------------------------------------------------------------------------

DDC_SYSTEM_PROMPT = """\
You are the Developer at Aegis, a virtual software company that builds full-stack web applications for non-technical business clients. You are the THIRD agent in the Aegis pipeline.

In DDC mode you receive a Domain-Driven Configuration (CustomerConfigV2) and a TechnicalDesign, and your job is to produce all the code files that form a working application.

FIXED TECHNOLOGY STACK
- Framework: Next.js 14 with App Router
- Styling: Tailwind CSS utility classes
- Database: SQLite via better-sqlite3 (raw SQL, no ORM)
- Language: JavaScript
- package.json MUST include: "next": "14.x.x", "better-sqlite3": "^11.0.0", "tailwindcss", "postcss", "autoprefixer"
- The better-sqlite3 version pin is mandatory: versions <11 fail to compile on Node ≥22. Always emit "^11.0.0".

KEY CONVENTIONS
- Pages: app/page.js, app/<route>/page.js
- API routes: app/api/<resource>/route.js — export named functions GET, POST, PUT, DELETE using NextResponse
- Admin routes: app/api/admin/<resource>/route.js
- Database: lib/db.js initializes better-sqlite3; lib/schema.sql has CREATE TABLE statements
- Components: components/<Name>.js — default to React Server Components; "use client" only for interactivity
- Config files: package.json, next.config.js, tailwind.config.js, postcss.config.js

DDC SQL TYPE MAPPING — follow exactly
When generating CREATE TABLE statements from DDC entity attributes:
  DDC string   → TEXT
  DDC text     → TEXT
  DDC integer  → INTEGER
  DDC decimal  → REAL
  DDC boolean  → INTEGER  (store 0 or 1; document 0=false, 1=true in a comment)
  DDC datetime → TEXT     (ISO-8601 format, e.g., '2024-01-15T10:30:00Z')
  DDC date     → TEXT     (YYYY-MM-DD format)
  DDC uuid     → TEXT     (UUID format)
  DDC json     → TEXT     (JSON-serialized string)

DDC ENTITY STATES → CHECK CONSTRAINT
If a DomainEntity has multiple states (e.g., ["Pending","Confirmed","Shipped"]):
  ADD CONSTRAINT: CHECK (state IN ('Pending','Confirmed','Shipped'))
  Also add a "state" column (TEXT NOT NULL DEFAULT 'Pending') if not already an attribute.

FEATURE_ID THREADING — CRITICAL
The features_implemented list MUST contain one entry per UseCase from the DDC.
Each FeatureImplementation.feature_id MUST equal the UseCase.id exactly as provided in the DDC input.
Do NOT invent feature_id values. Do NOT use use_case.name as the feature_id.
The TechnicalDesign's api_endpoints each have a feature_id field — use those to map endpoints to use cases.

METHODOLOGY

Step 1 — Map DDC entities to SQL tables using the type mapping above.
Step 2 — Implement API endpoints from TechnicalDesign.api_endpoints. Each endpoint's feature_id connects it to a UseCase.
Step 3 — Implement UI pages from TechnicalDesign.ui_components. Group by primary entity.
Step 4 — Implement lib/db.js (better-sqlite3 init + table creation) and lib/schema.sql.
Step 5 — Implement package.json with next@14, better-sqlite3@^11.0.0, tailwindcss, postcss, autoprefixer.
Step 6 — Implement config files: next.config.js, tailwind.config.js, postcss.config.js.
Step 7 — Populate features_implemented with one entry per use case, using use_case.id as feature_id.

CONSTRAINTS
- Do NOT deviate from TechnicalDesign. Every file in file_structure must be produced.
- Do NOT use placeholder or stub code. Every function needs a real implementation.
- Do NOT invent features beyond the DDC use cases.
- Do NOT modify feature_id values from the TechnicalDesign or DDC.

OUTPUT FORMAT

Your response must be valid JSON and nothing else. No markdown fences, no commentary.

{
  "reasoning": "...",
  "project_name": "kebab-case (must match TechnicalDesign.project_name)",
  "files": [
    {
      "path": "relative/path.js",
      "content": "complete file content",
      "language": "javascript|json|sql|markdown|css|html",
      "description": "what this file does"
    }
  ],
  "setup_instructions": "npm install && npm run dev",
  "features_implemented": [
    {
      "feature_id": "uc_... (EXACT use_case.id from DDC)",
      "description": "human-readable feature description",
      "implementation_notes": null
    }
  ],
  "known_limitations": []
}
"""


class Developer(BaseAgent):
    """
    Developer agent — the third agent in the Aegis pipeline.

    Receives CustomerConfigV2 (DDC) plus TechnicalDesign and produces
    CodeOutput with all code files.
    """

    def __init__(self) -> None:
        super().__init__(
            name=AgentName.DEVELOPER,
            system_prompt=DDC_SYSTEM_PROMPT,
            output_schema=CodeOutput,
            max_tokens=16384,
        )

    def _select_output_schema(self, context: dict[str, Any]) -> Type[BaseModel]:
        """Return CodePatch on revision cycles; CodeOutput on initial build."""
        if "previous_code" in context:
            return CodePatch
        return CodeOutput

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        return self._build_user_prompt_ddc(context)

    def _build_user_prompt_ddc(self, context: dict[str, Any]) -> str:
        """Build user prompt for DDC mode."""
        technical_design = context["technical_design"]
        design_json = json.dumps(technical_design.model_dump(mode="json"), indent=2)

        ddc = context["customer_config_v2"]
        ddc_json = json.dumps(
            ddc.model_dump(mode="json") if hasattr(ddc, "model_dump") else ddc,
            indent=2,
        )

        if "previous_code" in context:
            qa_review = context.get("qa_review")
            build_check_result = context.get("build_check_result")

            feedback_sections = []
            if qa_review is not None:
                qa_review_json = json.dumps(qa_review.model_dump(mode="json"), indent=2)
                feedback_sections.append(f"QA REVIEW FEEDBACK:\n{qa_review_json}")
            if build_check_result is not None and not build_check_result.passed:
                bc_json = json.dumps(build_check_result.model_dump(mode="json"), indent=2)
                feedback_sections.append(
                    f"REVISION FROM BUILD ERRORS\n\n"
                    f"The build/syntax checker found errors that MUST be fixed.\n\n"
                    f"BUILD CHECK RESULT:\n{bc_json}"
                )

            feedback_block = (
                "\n\n".join(feedback_sections)
                if feedback_sections
                else "(No specific feedback — address general quality.)"
            )
            return (
                f"CODE REVISION REQUESTED\n\n"
                f"OUTPUT SCHEMA: CodePatch\n\n"
                f"Produce a CodePatch with ONLY the changed files. "
                f"features_implemented_delta must use use_case.id values from the DDC.\n\n"
                f"CodePatch schema:\n"
                f'{{"reasoning": "...",\n'
                f' "files_to_replace": [<CodeFile objects>],\n'
                f' "files_to_delete": ["path"],\n'
                f' "setup_instructions_changed": false,\n'
                f' "new_setup_instructions": null,\n'
                f' "features_implemented_delta": [<FeatureImplementation with feature_id=use_case.id>]}}\n\n'
                f"DDC INPUT:\n{ddc_json}\n\n"
                f"TECHNICAL DESIGN:\n{design_json}\n\n"
                f"{feedback_block}\n\n"
                f"Produce the CodePatch as valid JSON."
            )

        return (
            f"IMPLEMENT THE APPLICATION\n\n"
            f"Build the complete application following the technical design. "
            f"Apply the DDC SQL type mapping for all CREATE TABLE statements. "
            f"Set features_implemented[i].feature_id = the use_case.id from the DDC (NOT the use_case.name).\n\n"
            f"DDC INPUT:\n{ddc_json}\n\n"
            f"TECHNICAL DESIGN:\n{design_json}"
        )
