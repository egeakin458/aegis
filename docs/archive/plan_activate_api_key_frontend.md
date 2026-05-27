# Plan: Activate API key auth — wire Authorization header in frontend
**Written against:** `main` @ 8395337
**Goal:** Send `Authorization: Bearer ${NEXT_PUBLIC_API_KEY}` on every frontend → backend call (REST, SSE, ZIP download) so we can safely set `API_KEY` on Railway.

---

## Background (read this before starting)

Backend auth is already wired via `backend/app/api/auth.py` and applied to every `/api/pipeline` route. When `settings.api_key` is non-empty, the dependency rejects requests missing `Authorization: Bearer <key>` with 401. Today `API_KEY` is unset on Railway so the backend is publicly triggerable (priority #0 in `STATUS.md`).

Frontend talks to the backend in three ways, and all three need the auth header:

1. **REST**: `frontend/lib/api/client.ts` — single `apiFetch<T>()` helper used by `startPipeline`, `submitClarification`, and `getOutput` (lines 1–28).
2. **SSE**: `frontend/lib/api/sse.ts` — `openSSE()` calls `fetchEventSource(url, { ... })` (lines 1–40). `@microsoft/fetch-event-source` accepts a `headers` option (unlike native `EventSource`), so the bearer token can be attached directly.
3. **ZIP download**: `frontend/components/output-viewer/index.tsx` line 82 builds `downloadUrl` as a plain string and renders an `<a href={downloadUrl} download>...</a>` (lines 95–102). Anchor tags cannot send custom headers, so this must become a JS `fetch` → `blob` → object-URL flow.

**Env var convention:** Next.js exposes only `NEXT_PUBLIC_*` vars to the browser bundle. The token is shipped in the JS bundle — that is acceptable for this project (single-customer thesis demo). It is a deterrent against drive-by abuse, not a strong secret.

**Deploy ordering matters** (this is the whole reason for the plan):

1. Land + merge frontend code with the header wired in.
2. Set `NEXT_PUBLIC_API_KEY` in Vercel project env, deploy frontend to Vercel.
3. Verify the deployed frontend works end-to-end against the still-public Railway backend.
4. **Only then** set `API_KEY` on Railway (same value as `NEXT_PUBLIC_API_KEY`). Railway will redeploy and start enforcing 401s — but the live frontend is already sending the header, so users see no break.

If you set `API_KEY` on Railway *first*, every browser still running the old frontend bundle starts getting 401s until their cached bundle expires. Don't do that.

**Gotchas:**
- `apiFetch` currently spreads `init?.headers` *after* `Content-Type` — the new code must keep that ordering and merge auth in the same place so callers can still override.
- `getApiKey()` returns `''` when the env var is absent. In that case, the helper must **not** add an `Authorization: Bearer ` header (a header with empty token is worse than no header — some proxies/CORS preflights treat it as malformed). Skip the header entirely when the key is empty so local dev (where the backend has `API_KEY=""`) keeps working.
- `fetchEventSource` does not auto-set `Content-Type` on GET; just adding `Authorization` is fine.
- Browser blob downloads need `URL.revokeObjectURL` cleanup to avoid leaks.
- The `<a>` had `download` attribute (no filename); the JS handler must set `a.download` to a sensible filename — backend serves `aegis-{run_id}.zip` via `Content-Disposition`, but blob downloads ignore server-side disposition, so we set it client-side.

---

### Task 1: Add `getApiKey()` helper and wire auth into `apiFetch`

**Files:**
- Modify: `frontend/lib/api/client.ts`

- [ ] **Step 1: Replace the full contents of `frontend/lib/api/client.ts` with the auth-aware version.**

```ts
import type { CustomerConfig, StartRunResponse, OutputManifest } from '@/lib/types/api'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const API = `${BASE_URL}/api/pipeline`

export function getApiKey(): string {
  return process.env.NEXT_PUBLIC_API_KEY ?? ''
}

export function authHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { Authorization: `Bearer ${key}` } : {}
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...init?.headers,
    },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${body ? ': ' + body : ''}`)
  }
  return res.json() as Promise<T>
}

export const startPipeline = (config: CustomerConfig): Promise<StartRunResponse> =>
  apiFetch('/start', { method: 'POST', body: JSON.stringify(config) })

export const submitClarification = (runId: string, answers: Record<string, string>): Promise<{ status: string }> =>
  apiFetch(`/${runId}/clarification`, { method: 'POST', body: JSON.stringify(answers) })

export const getOutput = (runId: string): Promise<OutputManifest> =>
  apiFetch(`/${runId}/output`)
```

Rationale: `authHeaders()` is exported so `sse.ts` and the download handler can reuse the exact same logic — single source of truth for "should we send a bearer token, and what is it". Caller-supplied `init?.headers` still wins (spread last) so future callers can override if needed.

---

### Task 2: Wire auth header into the SSE stream

**Files:**
- Modify: `frontend/lib/api/sse.ts`

- [ ] **Step 1: Replace the full contents of `frontend/lib/api/sse.ts` with the auth-aware version.**

```ts
import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { PipelineEvent } from '@/lib/types/api'
import type { ConnectionState } from '@/lib/types/ui'
import { authHeaders } from './client'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export interface SSEHandle {
  close: () => void
}

export interface SSECallbacks {
  onEvent: (event: PipelineEvent) => void
  onConnectionChange: (state: ConnectionState) => void
}

export function openSSE(runId: string, callbacks: SSECallbacks): SSEHandle {
  const controller = new AbortController()

  fetchEventSource(`${BASE_URL}/api/pipeline/${runId}/events`, {
    signal: controller.signal,
    openWhenHidden: true,
    headers: authHeaders(),
    onopen: async (res) => {
      if (res.ok) {
        callbacks.onConnectionChange('connected')
        return
      }
      throw new Error(`SSE open failed: ${res.status}`)
    },
    onmessage: (ev) => {
      if (!ev.data) return
      try {
        const event = JSON.parse(ev.data) as PipelineEvent
        callbacks.onEvent(event)
      } catch {}
    },
    onclose: () => {
      callbacks.onConnectionChange('disconnected')
    },
    onerror: (err) => {
      callbacks.onConnectionChange('reconnecting')
      if (err instanceof Error && err.message.startsWith('SSE open failed')) {
        throw err
      }
    },
  })

  return { close: () => controller.abort() }
}
```

Rationale: `fetchEventSource` accepts a top-level `headers` option (this is exactly why we use `@microsoft/fetch-event-source` instead of native `EventSource` — see CLAUDE.md "SSE → UI state").

---

### Task 3: Replace `<a href>` download with JS fetch+blob handler

**Files:**
- Modify: `frontend/components/output-viewer/index.tsx`

- [ ] **Step 1: Replace the full contents of `frontend/components/output-viewer/index.tsx` with the version that uses a JS-driven download.**

```tsx
'use client'
import { useState } from 'react'
import { X, Download, ChevronRight, ChevronDown, FileCode } from 'lucide-react'
import type { OutputManifest, OutputFile } from '@/lib/types/api'
import { authHeaders } from '@/lib/api/client'

interface Props {
  manifest: OutputManifest | null
  runId: string | null
  open: boolean
  onClose: () => void
}

interface TreeNode {
  name: string
  path: string
  file?: OutputFile
  children: Record<string, TreeNode>
}

function buildTree(files: OutputFile[]): TreeNode {
  const root: TreeNode = { name: '', path: '', children: {} }
  for (const file of files) {
    const parts = file.path.split('/')
    let node = root
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      if (!node.children[part]) {
        node.children[part] = { name: part, path: parts.slice(0, i + 1).join('/'), children: {} }
      }
      node = node.children[part]
      if (i === parts.length - 1) node.file = file
    }
  }
  return root
}

function TreeNodeRow({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: TreeNode
  depth: number
  selected: string | null
  onSelect: (file: OutputFile) => void
}) {
  const [open, setOpen] = useState(true)
  const isDir = !node.file
  const isSelected = selected === node.path

  if (isDir && Object.keys(node.children).length === 0) return null

  return (
    <div>
      <button
        onClick={() => (isDir ? setOpen(o => !o) : onSelect(node.file!))}
        className={`flex items-center gap-1.5 w-full text-left px-2 py-1 rounded text-xs transition-colors
          ${isSelected ? 'bg-aegis-accent/20 text-aegis-accent' : 'text-slate-300 hover:bg-slate-800'}`}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        {isDir
          ? (open ? <ChevronDown size={12} className="shrink-0 text-slate-500" /> : <ChevronRight size={12} className="shrink-0 text-slate-500" />)
          : <FileCode size={12} className="shrink-0 text-slate-500" />}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && open && Object.values(node.children).map(child => (
        <TreeNodeRow key={child.path} node={child} depth={depth + 1} selected={selected} onSelect={onSelect} />
      ))}
    </div>
  )
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export function OutputViewer({ manifest, runId, open, onClose }: Props) {
  const [selectedFile, setSelectedFile] = useState<OutputFile | null>(null)
  const [downloading, setDownloading] = useState(false)

  if (!open) return null

  const tree = manifest ? buildTree(manifest.files) : null

  async function handleDownload() {
    if (!runId || downloading) return
    setDownloading(true)
    try {
      const res = await fetch(`${BASE_URL}/api/pipeline/${runId}/output/download`, {
        headers: authHeaders(),
      })
      if (!res.ok) {
        const body = await res.text().catch(() => '')
        throw new Error(`${res.status} ${res.statusText}${body ? ': ' + body : ''}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `aegis-${runId}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download failed:', err)
      alert(`Download failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/50" onClick={onClose} />

      {/* Drawer */}
      <div className="w-[680px] bg-[#0f172a] border-l border-slate-800 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
          <span className="text-sm font-semibold text-slate-200">Generated Files</span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              disabled={!runId || downloading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Download size={13} />
              {downloading ? 'Downloading...' : 'Download ZIP'}
            </button>
            <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* File tree */}
          <div className="w-56 shrink-0 border-r border-slate-800 overflow-y-auto py-2">
            {tree && Object.values(tree.children).map(child => (
              <TreeNodeRow
                key={child.path}
                node={child}
                depth={0}
                selected={selectedFile?.path ?? null}
                onSelect={setSelectedFile}
              />
            ))}
            {!manifest && (
              <p className="text-xs text-slate-600 px-3 py-2">Loading...</p>
            )}
          </div>

          {/* File content */}
          <div className="flex-1 overflow-auto p-4">
            {selectedFile ? (
              <>
                <p className="text-xs text-slate-500 mb-2 font-mono">{selectedFile.path}</p>
                {selectedFile.content ? (
                  <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
                    {selectedFile.content}
                  </pre>
                ) : (
                  <p className="text-xs text-slate-500 italic">File too large to preview.</p>
                )}
              </>
            ) : (
              <p className="text-xs text-slate-600 mt-8 text-center">Select a file to view its contents.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
```

Notes on what changed:
- Added `import { authHeaders } from '@/lib/api/client'`.
- Removed the `downloadUrl` const.
- Replaced the `<a href>` with a `<button onClick={handleDownload}>` that streams the response into a blob and triggers a synthetic anchor click.
- Added `downloading` state so the button disables while the request is in flight (large generated apps can take a couple seconds to zip server-side).
- Filename is set client-side to `aegis-{run_id}.zip`.

---

### Task 4: Document the env var

**Files:**
- Modify: `frontend/.env.example`

- [ ] **Step 1: Replace the full contents of `frontend/.env.example`.**

```
NEXT_PUBLIC_API_URL=http://localhost:8000
# Bearer token sent as `Authorization: Bearer <key>` on every backend call.
# Must match `API_KEY` set on the backend (Railway env var). Leave empty for
# local dev when the backend is running with API_KEY="" (auth disabled).
NEXT_PUBLIC_API_KEY=
```

---

### Task 5: Local smoke test (manual)

- [ ] **Step 1: From `backend/`, start the backend with auth enabled.**

```bash
cd /home/ege/projects/aegis/backend
API_KEY=local-test-key uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: In a second terminal, confirm an unauthenticated request is rejected.**

```bash
curl -i -X POST http://localhost:8000/api/pipeline/start -H 'Content-Type: application/json' -d '{}'
```

Expect `HTTP/1.1 401 Unauthorized`.

- [ ] **Step 3: From `frontend/`, set the matching key and start dev server.**

```bash
cd /home/ege/projects/aegis/frontend
echo 'NEXT_PUBLIC_API_KEY=local-test-key' >> .env.local
npm run dev
```

- [ ] **Step 4: In the browser at `http://localhost:3000`, run a pipeline end-to-end.** Verify:
  - Intake submission succeeds (no 401 toast).
  - SSE console fills with events (no `reconnecting` flicker).
  - When the run completes, "Download ZIP" produces a file named `aegis-<run_id>.zip` and DevTools Network tab shows `Authorization: Bearer local-test-key` on the download request.

- [ ] **Step 5: Tear down the local override.**

```bash
cd /home/ege/projects/aegis/frontend
sed -i '/^NEXT_PUBLIC_API_KEY=local-test-key$/d' .env.local
```

---

### Task 6: Commit the frontend changes

- [ ] **Step 1: Stage and commit.**

```bash
cd /home/ege/projects/aegis
git add frontend/lib/api/client.ts frontend/lib/api/sse.ts frontend/components/output-viewer/index.tsx frontend/.env.example
git commit -m "feat(frontend): wire Authorization: Bearer header into REST, SSE, and ZIP download"
```

---

### Task 7: Deploy frontend to Vercel BEFORE setting Railway `API_KEY`

This is the order-sensitive part. Do not skip steps.

- [ ] **Step 1: In the Vercel project settings, add a Production env var.**
  - Name: `NEXT_PUBLIC_API_KEY`
  - Value: a freshly generated random string (e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"`). Save this value — it is needed in Step 4.
  - Also set `NEXT_PUBLIC_API_URL` to the live Railway backend URL if not already set.

- [ ] **Step 2: Push the commit / trigger a Vercel deploy.**

```bash
cd /home/ege/projects/aegis
git push origin main
```

- [ ] **Step 3: Wait for the Vercel build to finish, then verify the deployed frontend works against the still-public Railway backend.** Open the production URL, run a pipeline, confirm no 401s in the browser network tab. (Backend is still public at this point — auth header is being sent but ignored. That is expected.)

- [ ] **Step 4: In the Railway project, set `API_KEY` to the same value used in Step 1. Save — Railway redeploys automatically.**

- [ ] **Step 5: After Railway finishes redeploying, hit the public Railway URL directly with `curl` and confirm 401.**

```bash
curl -i -X POST https://<railway-host>/api/pipeline/start -H 'Content-Type: application/json' -d '{}'
```

Expect `401 Unauthorized`. Then re-run a pipeline from the deployed Vercel frontend and confirm it still works end-to-end (auth header now being enforced and accepted).

---

### Task 8: Mark item #0 complete in `STATUS.md`

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Edit the priority table — change item #0 status from `☐` to `✓` and refresh the urgent banner.**

Change the line:

```
| 0 | **URGENT: Activate API key auth** — `API_KEY` not set on Railway; wire `Authorization` header in frontend, then set env var | `client.ts`, `sse.ts`, `output-viewer/index.tsx`, Railway env vars | ☐ |
```

to:

```
| 0 | **Activate API key auth** — `Authorization: Bearer` header wired in frontend (REST + SSE + ZIP download); `API_KEY` set on Railway | `client.ts`, `sse.ts`, `output-viewer/index.tsx`, Railway env vars | ✓ |
```

And in the "Current Focus" section, replace the urgent line:

```
**Urgent: API key auth code is in place but `API_KEY` env var is not set on Railway — backend is publicly triggerable. Fix is item #0.**
```

with:

```
API key auth fully active: frontend sends `Authorization: Bearer ${NEXT_PUBLIC_API_KEY}` on all calls (REST, SSE, ZIP download); Railway `API_KEY` set and enforced.
```

Also append to the "What shipped (2026-05-08)" bullet list:

```
- API key auth activated: `Authorization` header wired into `client.ts`/`sse.ts`/`output-viewer`; ZIP download converted to fetch+blob; `API_KEY` set on Railway after Vercel deploy
```

- [ ] **Step 2: Commit the status update.**

```bash
cd /home/ege/projects/aegis
git add STATUS.md
git commit -m "chore(status): mark API key auth activation complete"
git push origin main
```
