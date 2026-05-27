import type { StartRunResponse, OutputManifest, LaunchStatus } from '@/lib/types/api'
import type { CustomerConfigV2 } from '@/lib/schemas/ddc'

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

export const startPipeline = (config: CustomerConfigV2): Promise<StartRunResponse> =>
  apiFetch('/start', { method: 'POST', body: JSON.stringify(config) })

export const submitClarification = (runId: string, answers: Record<string, string>): Promise<{ status: string }> =>
  apiFetch(`/${runId}/clarification`, { method: 'POST', body: JSON.stringify(answers) })

export const getOutput = (runId: string): Promise<OutputManifest> =>
  apiFetch(`/${runId}/output`)

// --- Generated-app launcher ---

export const launchApp = (runId: string): Promise<LaunchStatus> =>
  apiFetch(`/${runId}/launch`, { method: 'POST' })

export const stopApp = (): Promise<LaunchStatus> =>
  apiFetch('/launcher/stop', { method: 'POST' })

export const getLauncherState = (): Promise<LaunchStatus> =>
  apiFetch('/launcher/state')
