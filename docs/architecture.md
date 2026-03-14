# Aegis — Architecture Documentation

> This document will be expanded during development. See `Aegis_Research_Decisions_Plan.md` for the full technical plan.

## System Overview

Aegis is a 4-agent linear pipeline with feedback loops:

```
Customer Intake Form
        │
        ▼
┌─────────────────────┐
│ Requirements Analyst │◄──── Clarification loop with customer (max 3 rounds)
└─────────┬───────────┘
          │ Finalized Config (JSON)
          ▼
┌─────────────────────┐
│ Solution Architect   │◄──── Design revision from QA (max 1 cycle)
└─────────┬───────────┘
          │ Technical Design (JSON)
          ▼
┌─────────────────────┐
│ Developer            │◄──── Code revision from QA (max 2 cycles)
└─────────┬───────────┘
          │ Code Files (JSON manifest)
          ▼
┌─────────────────────┐
│ QA Reviewer          │───── Can request revision or approve
└─────────┬───────────┘
          │
          ▼
    Final Output
```

## Data Flow

All inter-agent communication uses structured JSON validated by Pydantic schemas.
See `backend/app/schemas/` for all data contracts.
