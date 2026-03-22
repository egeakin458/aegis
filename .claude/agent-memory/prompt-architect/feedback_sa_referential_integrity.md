---
name: SA referential integrity constraint pattern
description: Cross-referencing requirement across data models, endpoints, UI components, and file structure prevents orphan elements
type: feedback
---

For the Solution Architect prompt, include explicit referential integrity constraints: every model referenced by an endpoint must exist in data_models, every endpoint referenced in a UI component's data_sources must exist in api_endpoints, every component/endpoint must have a file in file_structure. Also constrain the reverse: no orphan endpoints serving no UI, no files with no corresponding design element.

**Why:** Without cross-referencing constraints, the SA commonly produces designs with orphan endpoints (API routes no page calls), phantom models (referenced in endpoints but never defined), and incomplete file structures. This creates cascading failures in the Developer agent, which either invents missing pieces or crashes on inconsistency.

**How to apply:** Include this in both CONSTRAINTS ("must ALWAYS ensure referential consistency") and QUALITY CRITERIA (list orphan elements as a weakness). The METHODOLOGY should order design steps so dependencies flow naturally: data models -> API endpoints -> UI components -> file structure.
