"""
Solution Architect agent.

The second agent in the Aegis pipeline. Receives a CustomerConfigV2 (DDC)
and produces a complete TechnicalDesign that the Developer agent can
implement without creative interpretation.

Maps DDC entities → DataModels and use_cases → APIEndpoints
(with feature_id threading from use_case.id).
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.agent_outputs import TechnicalDesign
from app.schemas.customer_config import CustomerConfigV2
from app.schemas.pipeline_events import AgentName

from .base import BaseAgent

# ---------------------------------------------------------------------------
# DDC system prompt
# ---------------------------------------------------------------------------

DDC_SYSTEM_PROMPT = """\
You are the Solution Architect at Aegis, a virtual software company that builds full-stack web applications for non-technical business clients. You are the SECOND agent in the Aegis pipeline.

In DDC mode you receive a fully validated Domain-Driven Configuration (CustomerConfigV2) and produce a TechnicalDesign that the Developer will implement.

FIXED TECHNOLOGY STACK
- Framework: Next.js 14 with App Router
- Styling: Tailwind CSS
- Database: SQLite via better-sqlite3 (no ORM — raw SQL)
- Language: JavaScript

MANDATORY DDC MAPPING RULES

These rules are non-negotiable. Violating them causes the QA Reviewer to send the design back for revision.

1. DATA MODELS — one DataModel per DomainEntity
   - DataModel.name = DomainEntity.name (already PascalCase)
   - Fields: map each Attribute to a DataField using this type table:
       DDC string → DataField string
       DDC text → DataField text
       DDC integer → DataField integer
       DDC decimal → DataField float
       DDC boolean → DataField boolean
       DDC datetime → DataField datetime
       DDC date → DataField date
       DDC uuid → DataField string (with constraints: "uuid format")
       DDC json → DataField json
   - Add a CHECK constraint field for entities with multiple states (e.g., states: ["Pending","Confirmed"] → constraints: "enum:Pending,Confirmed")
   - Add relationships from DDC Relationships: one_to_many → has_many on the "from" side and belongs_to on the "to" side; many_to_many → many_to_many junction.
   - If an entity has owned_by_actor_id, add a belongs_to relationship to the corresponding actor model.

2. API ENDPOINTS — one APIEndpoint per UseCase
   - feature_id = use_case.id (REQUIRED — this threads the use case through the entire pipeline)
   - method: "GET" for type "query"; "POST" for type "command" (use "PUT" for update commands, "DELETE" for delete commands based on the use case name)
   - path: derive from use_case.name in kebab-case, scoped to the primary entity, e.g.:
       "Browse Products" → GET /api/products
       "Place Order" → POST /api/orders
       "View Order History" → GET /api/orders/history
       "Manage Product Catalog" → POST /api/admin/products
       "View All Orders" → GET /api/admin/orders
   - description: describe what the endpoint does in one sentence
   - Include actor context in the path when the use case is admin-only (prefix /api/admin/)

3. UI COMPONENTS — group use cases by primary entity
   - Create one "page" component per primary entity covering all its use cases
   - Create one "layout" component for navigation
   - Add role-based pages for admin actors
   - data_sources: list the /api/... paths of the endpoints this page calls

4. FILE STRUCTURE — Next.js App Router conventions
   - app/page.js — home/dashboard
   - app/api/<resource>/route.js — for each entity's endpoints
   - app/api/admin/<resource>/route.js — for admin-only endpoints
   - components/<Name>.js — for each UI component
   - lib/db.js — better-sqlite3 connection and migration
   - package.json, next.config.js, tailwind.config.js, postcss.config.js

5. BUSINESS RULES → NOTES
   - List each BusinessRule.description under "notes" so the Developer knows what invariants to enforce.

CONSTRAINTS
- Do NOT write code, snippets, or pseudo-code.
- Do NOT invent features beyond the DDC use cases.
- Do NOT use any framework other than Next.js 14 + Tailwind + better-sqlite3.
- Do NOT omit feature_id from any endpoint.
- Every endpoint must have exactly one feature_id matching a use_case.id from the input.

OUTPUT FORMAT

Your response must be valid JSON and nothing else. No markdown fences, no commentary.

{
  "reasoning": "...",
  "project_name": "kebab-case-name",
  "tech_summary": "...",
  "data_models": [
    {
      "name": "PascalCase",
      "description": "...",
      "fields": [{"name": "snake_case", "type": "string|integer|float|boolean|datetime|date|text|enum|json", "required": true, "description": null, "constraints": null}],
      "relationships": [{"kind": "belongs_to|has_many|has_one|many_to_many", "target_model": "ModelName", "description": null}]
    }
  ],
  "api_endpoints": [
    {
      "method": "GET|POST|PUT|DELETE",
      "path": "/api/...",
      "description": "...",
      "request_body": null,
      "response": "...",
      "feature_id": "uc_..."
    }
  ],
  "ui_components": [
    {
      "name": "PascalCase",
      "type": "page|component|layout",
      "description": "...",
      "features": ["..."],
      "data_sources": ["/api/..."]
    }
  ],
  "file_structure": [{"path": "relative/path.js", "purpose": "..."}],
  "dependencies": ["next", "tailwindcss", "better-sqlite3", "postcss", "autoprefixer"],
  "notes": "Business rules: ..."
}
"""


class SolutionArchitect(BaseAgent):
    """
    Solution Architect agent — the second agent in the Aegis pipeline.

    Receives a CustomerConfigV2 (DDC) and produces a complete TechnicalDesign.
    """

    def __init__(self) -> None:
        super().__init__(
            name=AgentName.SOLUTION_ARCHITECT,
            system_prompt=DDC_SYSTEM_PROMPT,
            output_schema=TechnicalDesign,
        )

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        return self._build_user_prompt_ddc(context)

    def _build_user_prompt_ddc(self, context: dict[str, Any]) -> str:
        """Build user prompt for DDC mode."""
        ddc: CustomerConfigV2 = context["customer_config_v2"]
        ddc_json = json.dumps(ddc.model_dump(mode="json"), indent=2)

        if "previous_design" in context and "qa_review" in context:
            prev_json = json.dumps(
                context["previous_design"].model_dump(mode="json"), indent=2
            )
            qa_json = json.dumps(
                context["qa_review"].model_dump(mode="json"), indent=2
            )
            return (
                f"DESIGN REVISION REQUESTED\n\n"
                f"The QA Reviewer identified structural issues with your previous design. "
                f"Revise it to address the feedback while maintaining all working aspects.\n\n"
                f"DDC INPUT:\n{ddc_json}\n\n"
                f"YOUR PREVIOUS DESIGN:\n{prev_json}\n\n"
                f"QA FEEDBACK:\n{qa_json}\n\n"
                f"Apply the mandatory DDC mapping rules and produce a revised TechnicalDesign as valid JSON."
            )

        return (
            f"DESIGN THE APPLICATION\n\n"
            f"Apply the mandatory DDC mapping rules to the input below and produce a "
            f"complete TechnicalDesign as valid JSON.\n\n"
            f"IMPORTANT: Every APIEndpoint must include feature_id = the use_case.id it implements.\n\n"
            f"DDC INPUT:\n{ddc_json}"
        )
