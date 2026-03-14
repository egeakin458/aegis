# Aegis — Virtual Software Company

A multi-agent AI pipeline that operates as a virtual software company, producing full-stack web applications from plain-language business requirements.

**Senior Thesis Project** — Izmir University of Economics, Department of Computer Engineering

## Architecture

```
Customer → Intake Form → Requirements Analyst → Solution Architect → Developer → QA Reviewer → Output
                              ↑                                          |              |
                              |                    Code revision (max 2) ←──────────────┤
                              |                    Design revision (max 1) ←────────────┘
```

## Tech Stack

- **Backend:** Python 3.12 + FastAPI
- **Frontend:** Next.js 14+ + Tailwind CSS + shadcn/ui
- **LLM:** Anthropic Claude API (Sonnet 4.5 + Haiku 4.5)
- **Real-time:** Server-Sent Events (SSE)
- **Database:** SQLite + filesystem

## Quick Start

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Then edit .env with your API key
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Project Structure

See `CLAUDE.md` for full project context and current implementation status.
