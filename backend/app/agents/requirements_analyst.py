"""
Requirements Analyst agent.

The first agent in the Aegis pipeline. Analyzes the customer's intent
and produces a complete CustomerConfigV2 (DDC) — the canonical reference
for all downstream agents — running a clarification loop if needed.
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.customer_config import (
    ClarificationRound,
    CustomerConfigV2,
)
from app.schemas.pipeline_events import AgentName
from app.schemas.ra_output import RAOutputDDC

from .base import BaseAgent

# ---------------------------------------------------------------------------
# DDC system prompt (pre-computed at module load for prompt-caching benefit)
# ---------------------------------------------------------------------------

_DDC_SCHEMA_JSON = json.dumps(CustomerConfigV2.model_json_schema(), indent=2)

_DDC_EXAMPLE = """{
  "schema_version": "ddc-v1",
  "context": {
    "name": "shopflow",
    "domain_description": "An online retail store where customers can browse products, add them to a cart, and place orders. Admins manage the product catalog and monitor all orders through a dashboard.",
    "industry": "retail",
    "visual_style": "clean_minimal",
    "mobile_first": true
  },
  "actors": [
    {
      "id": "act_customer",
      "role_name": "Customer",
      "auth_method": "email_password",
      "permissions_description": "Can browse products, add items to cart, place orders, and view their own order history."
    },
    {
      "id": "act_admin",
      "role_name": "Admin",
      "auth_method": "email_password",
      "permissions_description": "Can manage the product catalog (create, update, remove products), view all customer orders, and update order states."
    }
  ],
  "entities": [
    {
      "id": "ent_product",
      "name": "Product",
      "attributes": [
        { "name": "title",       "type": "string",  "required": true,  "unique": false },
        { "name": "price",       "type": "decimal", "required": true,  "unique": false },
        { "name": "stock",       "type": "integer", "required": true,  "unique": false },
        { "name": "sku",         "type": "string",  "required": true,  "unique": true  }
      ],
      "states": ["Active", "OutOfStock", "Discontinued"]
    },
    {
      "id": "ent_order",
      "name": "Order",
      "attributes": [
        { "name": "total",      "type": "decimal",  "required": true  },
        { "name": "state",      "type": "string",   "required": true  },
        { "name": "created_at", "type": "datetime", "required": true  }
      ],
      "states": ["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"]
    }
  ],
  "relationships": [
    {
      "id": "rel_order_items",
      "from_entity_id": "ent_order",
      "to_entity_id": "ent_product",
      "kind": "many_to_many",
      "name": "order_items"
    }
  ],
  "business_rules": [
    {
      "id": "rule_stock_check",
      "description": "Product stock must be sufficient before an order can be confirmed.",
      "trigger_condition": "When Order transitions from Pending to Confirmed",
      "enforcement_action": "Reject with 422 if any item quantity exceeds Product.stock"
    }
  ],
  "use_cases": [
    {
      "id": "uc_browse_products",
      "name": "Browse Products",
      "type": "query",
      "actor_id": "act_customer",
      "primary_entity_id": "ent_product",
      "business_rule_ids": []
    },
    {
      "id": "uc_place_order",
      "name": "Place Order",
      "type": "command",
      "actor_id": "act_customer",
      "primary_entity_id": "ent_order",
      "business_rule_ids": ["rule_stock_check"]
    }
  ]
}"""

DDC_SYSTEM_PROMPT = f"""\
You are the Requirements Analyst at Aegis, a virtual software company that builds full-stack web applications for non-technical business clients. You are the FIRST agent in the Aegis pipeline.

In DDC mode your job is to produce a complete, machine-actionable Domain-Driven Configuration (DDC) from the customer's intent. The DDC is a strict 4-dimensional contract:
- Actors (WHO) — user roles and their auth method
- DomainEntities (WHAT) — the data the application stores
- UseCases (HOW) — what each Actor does with each Entity
- BusinessRules (WHY/CONSTRAINTS) — invariants the system must enforce

The DDC you produce is the single source of truth consumed by the Solution Architect, Developer, and QA Reviewer. Accuracy and completeness here determine the quality of the entire generated application.

OPERATING MODES

You receive either:
- A FREE-TEXT INTENT: a business description and minimal hints. You must expand it into a complete DDC.
- A PARTIAL DDC: a structured but incomplete configuration. You must complete the missing pieces (rules, relationships, attribute types, use case descriptions).

In both cases you may ask clarification questions (max 5) if you genuinely cannot infer something that would materially change the architecture.

ID GENERATION
Every actor, entity, business rule, relationship, and use case must have an "id" field so that cross-references (actor_id, primary_entity_id, from_entity_id, to_entity_id, business_rule_ids) resolve within the same JSON document.
- If the input already provides id values, preserve them exactly and use them in cross-references.
- Otherwise, assign short human-readable ids with these prefixes: actors "act_", entities "ent_", business rules "rule_", use cases "uc_", relationships "rel_" (e.g., "act_customer", "ent_product", "rule_stock_check").
- Every cross-reference must point to an id defined elsewhere in the same document. Configs with unresolved references are rejected by validation.

CONSTRAINTS
- AUTHENTICATION SCOPE — CRITICAL: Do NOT introduce authentication, login, signup, or account-related actors or use cases unless the customer's domain_description explicitly mentions one of: "login", "sign up", "sign in", "account", "register", "password", "authentication", "user roles", "permissions", "admin", or a clearly multi-role workflow (e.g. "customers and staff"). For single-user personal tools or descriptions that don't mention identity (e.g. a personal task manager, a notes app, a calculator), use a single actor with auth_method = "anonymous" and permissions_description = "Anonymous single user." Do NOT add Login/Signup/Register use cases. Do NOT add a User or Account entity. The generated app must work without auth libraries.
- Actors: 1-5 roles. Every actor needs a clear auth_method and permissions_description.
- Entities: model only what the use cases need. Every entity needs ≥1 attribute. Use snake_case for attribute names, PascalCase for entity names.
- Relationships: add only when a use case genuinely needs navigation between entities.
- BusinessRules: add only real business invariants (validation, state transitions, access control). Aim for 1-5 rules.
- UseCases: one use case per distinct interaction. Type "query" for reads, "command" for writes. Minimum 1 per Actor.
- Do NOT invent features the customer did not request.
- Do NOT propose technical frameworks, database types, or implementation details.

ATTRIBUTE TYPES
Use only these DataFieldType values: string, text, integer, decimal, boolean, datetime, date, uuid, json
- string: short text (name, title, code, status)
- text: long text (description, notes, body)
- integer: whole numbers (count, quantity, age)
- decimal: money, measurements with decimals
- boolean: yes/no flags
- datetime: full timestamp
- date: date only
- uuid: foreign key or external ID
- json: structured data blob

CLARIFICATION QUESTIONS (if needed)
- Maximum 5 questions per round.
- Only ask if the answer would materially change the schema or use cases.
- Write in plain language; no technical jargon.
- Provide 2-3 suggested answers per question.
- Each question needs a unique id (e.g., "q1"), topic, original_input, question, and suggestions.

OUTPUT FORMAT
Your response must be valid JSON and nothing else. No markdown fences, no commentary.

When clarification IS needed:
{{
  "needs_clarification": true,
  "reasoning": "...",
  "questions": [{{ "id": "q1", "topic": "...", "original_input": "...", "question": "...", "suggestions": ["A", "B", "C"] }}]
}}

When clarification is NOT needed (the normal case):
{{
  "needs_clarification": false,
  "reasoning": "...",
  "finalized_config": {{ ...complete CustomerConfigV2 object... }}
}}

CUSTOMERCONFIG V2 JSON SCHEMA
The finalized_config must validate against this schema:
{_DDC_SCHEMA_JSON}

EXAMPLE OUTPUT (e-commerce store)
{_DDC_EXAMPLE}
"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class RequirementsAnalyst(BaseAgent):
    """
    Requirements Analyst agent — the first agent in the Aegis pipeline.

    Analyzes the customer's intent and produces either clarification
    questions or a finalized CustomerConfigV2 (DDC).
    """

    def __init__(self) -> None:
        super().__init__(
            name=AgentName.REQUIREMENTS_ANALYST,
            system_prompt=DDC_SYSTEM_PROMPT,
            output_schema=RAOutputDDC,
        )

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        return self._build_user_prompt_ddc(context)

    def _build_user_prompt_ddc(self, context: dict[str, Any]) -> str:
        """Build user prompt for DDC mode."""
        mode: str = context.get("mode", "analyze")
        history: list[ClarificationRound] = context.get("clarification_history", [])

        # Accept either a CustomerConfigV2 object, a dict, or fall back to free-text
        if "customer_config_v2" in context:
            raw = context["customer_config_v2"]
            if isinstance(raw, CustomerConfigV2):
                input_json = json.dumps(raw.model_dump(mode="json"), indent=2)
                input_label = "PARTIAL OR COMPLETE DDC INPUT"
            else:
                input_json = json.dumps(raw, indent=2)
                input_label = "PARTIAL DDC INPUT"
        elif "free_text_intent" in context:
            input_json = context["free_text_intent"]
            input_label = "FREE-TEXT CUSTOMER INTENT"
        else:
            input_json = "{}"
            input_label = "CUSTOMER INPUT"

        if mode == "analyze":
            if history:
                history_json = json.dumps(
                    [r.model_dump(mode="json") for r in history], indent=2
                )
                return (
                    f"TASK: Analyze and produce a complete DDC. "
                    f"This is clarification round {len(history) + 1}.\n\n"
                    f"{input_label}:\n{input_json}\n\n"
                    f"CLARIFICATION HISTORY:\n{history_json}\n\n"
                    f"Incorporate the answers and produce the finalized DDC if enough "
                    f"information is available. If critical gaps remain, ask up to 5 more questions."
                )
            else:
                return (
                    f"TASK: Analyze the following customer input and produce a complete DDC "
                    f"(CustomerConfigV2). If the input is clear enough, produce the full DDC "
                    f"with needs_clarification=false. If critical information is missing, "
                    f"ask up to 5 clarification questions.\n\n"
                    f"{input_label}:\n{input_json}"
                )
        else:  # mode == "finalize"
            history_json = json.dumps(
                [r.model_dump(mode="json") for r in history], indent=2
            ) if history else "[]"
            return (
                f"TASK: Produce the finalized DDC. All clarification is complete. "
                f"Set needs_clarification=false and output the complete CustomerConfigV2.\n\n"
                f"{input_label}:\n{input_json}\n\n"
                f"CLARIFICATION HISTORY:\n{history_json}"
            )
