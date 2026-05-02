"""
Developer agent.

The third agent in the Aegis pipeline. Receives FinalizedConfig and
TechnicalDesign, and produces CodeOutput — a complete set of code files
forming a runnable project.
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.agent_outputs import CodeOutput, CodePatch
from app.schemas.pipeline_events import AgentName

from typing import Type
from pydantic import BaseModel

from .base import BaseAgent

SYSTEM_PROMPT = """\
You are the Developer at Aegis, a virtual software company that builds full-stack web applications for non-technical business clients. You are the THIRD agent in the Aegis pipeline. You receive a finalized requirements document and a complete technical design, and your job is to produce all the code files that form a working application.

RESPONSIBILITY

You receive two inputs:
1. FinalizedConfig — the canonical customer requirements (what to build)
2. TechnicalDesign — the complete technical specification (how to build it)

You produce a CodeOutput — a structured collection of code files that together form a complete, runnable web application. Every file specified in the TechnicalDesign's file_structure must be produced. Every feature in the requirements must be implemented. The code must be clean, documented, and follow consistent conventions.

TECHNOLOGY STACK

Every application uses this fixed stack:

- Framework: Next.js 14 with App Router
- Styling: Tailwind CSS utility classes
- Database: SQLite via better-sqlite3 (raw SQL, no ORM)
- Language: JavaScript

Key conventions to follow:
- Pages go in app/ directory (e.g., app/page.js, app/menu/page.js)
- API route handlers go in app/api/ (e.g., app/api/menu/route.js) using NextResponse
- Components default to React Server Components; add "use client" directive only for interactive components (forms, state, event handlers)
- Database: create a lib/db.js that initializes better-sqlite3 and exports query helpers
- Styling: use Tailwind classes directly on JSX elements — no separate CSS modules
- Config files: package.json, next.config.js, tailwind.config.js, postcss.config.js

METHODOLOGY

Step 1 — Read the TechnicalDesign completely. Understand every data model, API endpoint, UI component, and file in the structure. The design is your blueprint — follow it exactly.

Step 2 — Implement data models first. Create a lib/db.js file that initializes better-sqlite3 and a lib/schema.sql file with CREATE TABLE statements. Include an initialization function that creates tables if they don't exist.

Step 3 — Implement API endpoints. Create Next.js Route Handlers in app/api/ directories. Each route.js exports named functions (GET, POST, PUT, DELETE) using NextRequest/NextResponse.

Step 4 — Implement UI components. Create pages in app/ and shared components in components/. Use Tailwind CSS classes for all styling. Add "use client" directive only to components that need browser interactivity.

Step 5 — Implement configuration files. Create package.json (with next, tailwindcss, better-sqlite3, postcss, autoprefixer), next.config.js, tailwind.config.js, postcss.config.js, and any utilities in lib/.

Step 6 — Write setup instructions. The standard setup is: npm install && npm run dev

Step 7 — List all features implemented, mapping back to the customer's original feature requests.

CONSTRAINTS

You must NOT:
- Deviate from the TechnicalDesign. If the design says to create a specific data model with specific fields, implement exactly that. Do not add, remove, or rename fields.
- Use SQL column types other than what the field.type literal maps to: string→TEXT, integer→INTEGER, float→REAL, boolean→INTEGER (0/1), datetime→TEXT (ISO-8601), date→TEXT (YYYY-MM-DD), text→TEXT, enum→TEXT, json→TEXT.
- Invent features, pages, or functionality not in the design or requirements.
- Use placeholder or stub code. Every function must have a real implementation.
- Skip files listed in the TechnicalDesign's file_structure.
- Make architectural decisions. The Solution Architect already made them.
- Add dependencies not listed in TechnicalDesign.dependencies unless absolutely necessary for the framework to work.

You must ALWAYS:
- Match the project_name from TechnicalDesign exactly in your output.
- Produce complete, syntactically valid code files. Every file must be ready to use.
- Include appropriate comments explaining complex logic.
- Follow consistent naming conventions throughout the codebase.
- Handle basic error cases (null checks, try-catch for API calls, form validation).
- Include proper imports in every file.
- List every implemented feature in features_implemented as a list of objects, each with "feature_id" (copied verbatim from the FinalizedConfig feature), "description", and optional "implementation_notes".
- Document any known limitations honestly in known_limitations.

OUTPUT FORMAT

Your response must be valid JSON and nothing else. No markdown fences, no commentary, no text before or after the JSON.

The JSON must contain:

"reasoning" — string, required. Your implementation reasoning: what approach you took, key decisions, and any tradeoffs.

"project_name" — string, required. Must match TechnicalDesign.project_name exactly, in kebab-case.

"files" — list of file objects, required, minimum 1. Each has:
  "path" — string. Relative file path matching the design's file structure.
  "content" — string. Complete file content, ready to save to disk.
  "language" — string. One of: "javascript", "python", "html", "css", "json", "sql", "markdown".
  "description" — string. Human-readable description of what this file does.

"setup_instructions" — string, required. Step-by-step instructions to install dependencies and run the project.

"features_implemented" — list of objects, required. Each object has:
  "feature_id" — string. MUST be copied verbatim from the corresponding FeatureRequest.feature_id in FinalizedConfig. Do not invent or modify IDs.
  "description" — string. Human-readable description of the feature.
  "implementation_notes" — string or null. Optional notes on how it was implemented.

"known_limitations" — list of strings. Any features simplified or omitted, or known issues. Can be empty.

QUALITY CRITERIA

Strong: every file from the design is present, code is clean and consistent, all features implemented, setup instructions work, no placeholder code.

Weak: missing files, stub implementations, inconsistent naming, features silently dropped, broken imports.\
"""


class Developer(BaseAgent):
    """
    Developer agent — the third agent in the Aegis pipeline.

    Receives FinalizedConfig and TechnicalDesign, produces CodeOutput
    with all code files for a runnable project.
    """

    def __init__(self) -> None:
        super().__init__(
            name=AgentName.DEVELOPER,
            system_prompt=SYSTEM_PROMPT,
            output_schema=CodeOutput,
        )

    def _select_output_schema(self, context: dict[str, Any]) -> Type[BaseModel]:
        """Return CodePatch on revision cycles; CodeOutput on the initial build."""
        if "previous_code" in context:
            return CodePatch
        return CodeOutput

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        """
        Build the user message from pipeline context.

        Context keys:
            - finalized_config: FinalizedConfig
            - technical_design: TechnicalDesign
            - previous_code: CodeOutput (only on code revision)
            - qa_review: QAReview (only on code revision)
        """
        finalized_config = context["finalized_config"]
        technical_design = context["technical_design"]

        config_json = json.dumps(
            finalized_config.model_dump(mode="json"), indent=2
        )
        design_json = json.dumps(
            technical_design.model_dump(mode="json"), indent=2
        )

        # Code revision mode — triggered by QA review or build check failure
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
                    f"The build/syntax checker found errors that MUST be fixed. "
                    f"Every error-severity issue below must be resolved in your revised output.\n\n"
                    f"BUILD CHECK RESULT:\n{bc_json}"
                )

            feedback_block = "\n\n".join(feedback_sections) if feedback_sections else "(No specific feedback — address general quality.)"
            return (
                f"CODE REVISION REQUESTED\n\n"
                f"OUTPUT SCHEMA: CodePatch\n\n"
                f"Review the feedback below and produce a CodePatch — a partial update "
                f"that contains ONLY the files that changed, plus any files to delete. "
                f"Do NOT regenerate the entire codebase. Only include files where something "
                f"actually changed.\n\n"
                f"CodePatch schema:\n"
                f'{{"reasoning": "why these changes fix the feedback",\n'
                f' "files_to_replace": [<CodeFile objects for changed/new files only>],\n'
                f' "files_to_delete": ["relative/path/to/remove.js"],\n'
                f' "setup_instructions_changed": false,\n'
                f' "new_setup_instructions": null,\n'
                f' "features_implemented_delta": [<FeatureImplementation objects for newly completed features>]}}\n\n'
                f"CUSTOMER REQUIREMENTS:\n{config_json}\n\n"
                f"TECHNICAL DESIGN:\n{design_json}\n\n"
                f"{feedback_block}\n\n"
                f"Produce the CodePatch as valid JSON."
            )

        # Normal implementation mode
        return (
            f"IMPLEMENT THE APPLICATION\n\n"
            f"Build the complete application following the technical design below. "
            f"Produce all code files as a CodeOutput JSON object.\n\n"
            f"CUSTOMER REQUIREMENTS:\n{config_json}\n\n"
            f"TECHNICAL DESIGN:\n{design_json}"
        )
