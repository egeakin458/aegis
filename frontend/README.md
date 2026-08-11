# Frontend

This is the Aegis frontend application. It connects to the backend pipeline and displays the live event stream for a running pipeline.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000` in your browser.

## What it includes

- pipeline dashboard and event console
- intake form UI for starting a run
- replay support via `?run=<run_id>`
- generated app preview and download workflow

## Notes

- The backend must be running before the frontend can start a pipeline.
- `frontend` is not a standalone app: it is the user-facing dashboard for the Aegis pipeline.
