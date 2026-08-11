# Aegis — Virtual Software Company

Aegis is a structured multi-agent AI pipeline that generates full-stack web applications from business requirements.

## What it does

A user supplies a domain-driven configuration. The pipeline uses four agents to convert that input into:
- a finalized requirements model
- a technical design
- generated application code
- a QA review and revision cycle

## Core architecture

- Backend: Python 3.12, FastAPI, SQLite
- Frontend: Next.js 14, Tailwind CSS, shadcn/ui
- LLM: Anthropic Claude API
- Real-time: SSE for pipeline event streaming
- Generated output: self-contained Next.js apps in `backend/outputs`

## Quick start

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set ANTHROPIC_API_KEY in .env
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Repository layout

- `backend/app` — backend application code
- `backend/tests` — backend tests
- `backend/build_sandbox` — isolated build-check sandbox for generated apps
- `backend/outputs` — generated app output directories
- `frontend` — user interface and pipeline dashboard
