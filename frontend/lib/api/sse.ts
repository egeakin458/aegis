import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { PipelineEvent } from '@/lib/types/api'
import type { ConnectionState } from '@/lib/types/ui'

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
    onopen: async (res) => {
      if (res.ok) {
        callbacks.onConnectionChange('connected')
        return
      }
      // Non-retryable errors (e.g. 404 run not found)
      throw new Error(`SSE open failed: ${res.status}`)
    },
    onmessage: (ev) => {
      if (!ev.data) return
      try {
        const event = JSON.parse(ev.data) as PipelineEvent
        callbacks.onEvent(event)
      } catch {
        // ignore malformed events / keepalive comment data
      }
    },
    onclose: () => {
      callbacks.onConnectionChange('disconnected')
    },
    onerror: (err) => {
      callbacks.onConnectionChange('reconnecting')
      // Throw to stop retrying on non-recoverable errors
      if (err instanceof Error && err.message.startsWith('SSE open failed')) {
        throw err
      }
      // Returning undefined lets fetch-event-source retry with backoff
    },
  })

  return { close: () => controller.abort() }
}
