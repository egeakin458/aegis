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
