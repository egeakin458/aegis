import type { CustomerConfig, StartRunResponse, OutputManifest } from '@/lib/types/api'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const API = `${BASE_URL}/api/pipeline`

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
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
