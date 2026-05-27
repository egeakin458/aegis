'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Rocket, Square, ExternalLink, AlertTriangle, Loader2 } from 'lucide-react'
import type { LaunchStatus } from '@/lib/types/api'
import { launchApp, stopApp, getLauncherState } from '@/lib/api/client'

interface Props {
  runId: string
}

const POLL_INTERVAL_MS = 1000
const TRANSITIONAL: ReadonlyArray<LaunchStatus['state']> = ['installing', 'starting', 'stopping']

function LabelForState({ state }: { state: LaunchStatus['state'] }) {
  switch (state) {
    case 'installing': return <>Installing dependencies (this can take ~60 s on first run)…</>
    case 'starting':   return <>Starting Next.js dev server…</>
    case 'stopping':   return <>Stopping…</>
    case 'running':    return <>App is running.</>
    case 'error':      return <>Launch failed.</>
    default:           return null
  }
}

export function LaunchPanel({ runId }: Props) {
  const [status, setStatus] = useState<LaunchStatus | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const openedRef = useRef<string | null>(null)

  // Initial fetch on mount.
  useEffect(() => {
    let cancelled = false
    getLauncherState()
      .then(s => { if (!cancelled) setStatus(s) })
      .catch(() => { if (!cancelled) setStatus({ state: 'idle', run_id: null, port: null, url: null, pid: null, started_at: null, error: null }) })
    return () => { cancelled = true }
  }, [])

  // Poll while transitional.
  useEffect(() => {
    if (!status || !TRANSITIONAL.includes(status.state)) return
    const id = setInterval(async () => {
      try {
        const next = await getLauncherState()
        setStatus(next)
      } catch {
        // network blip; keep polling
      }
    }, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [status])

  // Auto-open the URL once when we transition into running for THIS run.
  useEffect(() => {
    if (!status) return
    if (
      status.state === 'running' &&
      status.url &&
      status.run_id === runId &&
      openedRef.current !== status.url
    ) {
      openedRef.current = status.url
      window.open(status.url, '_blank', 'noopener,noreferrer')
    }
  }, [status, runId])

  const onLaunch = useCallback(async () => {
    if (submitting) return
    setSubmitting(true)
    try {
      const s = await launchApp(runId)
      setStatus(s)
    } catch (err) {
      setStatus({
        state: 'error',
        run_id: runId,
        port: null, url: null, pid: null, started_at: null,
        error: err instanceof Error ? err.message : String(err),
      })
    } finally {
      setSubmitting(false)
    }
  }, [runId, submitting])

  const onStop = useCallback(async () => {
    if (submitting) return
    setSubmitting(true)
    try {
      const s = await stopApp()
      setStatus(s)
      openedRef.current = null
    } catch (err) {
      console.error('Stop failed:', err)
    } finally {
      setSubmitting(false)
    }
  }, [submitting])

  if (!status) {
    // Quiet — initial fetch in flight.
    return null
  }

  const ownsRunning =
    status.state === 'running' && status.run_id === runId
  const someoneElseRunning =
    status.state === 'running' && status.run_id !== runId
  const transitional = TRANSITIONAL.includes(status.state)

  return (
    <div className="border-b border-slate-800 px-4 py-3 bg-slate-900/60">
      <div className="flex items-center gap-3">
        <Rocket size={14} className="text-emerald-400 shrink-0" />
        <div className="flex-1 min-w-0">
          {ownsRunning && status.url ? (
            <div className="flex items-center gap-2 text-xs text-slate-200">
              <span>Running at</span>
              <a
                href={status.url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1"
              >
                {status.url}
                <ExternalLink size={11} />
              </a>
            </div>
          ) : transitional ? (
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <Loader2 size={12} className="animate-spin text-cyan-400" />
              <LabelForState state={status.state} />
            </div>
          ) : status.state === 'error' ? (
            <div className="flex items-start gap-2 text-xs text-rose-300">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span className="truncate" title={status.error ?? undefined}>{status.error ?? 'Launch failed.'}</span>
            </div>
          ) : someoneElseRunning ? (
            <span className="text-xs text-slate-400">
              Another run’s app is running. Click <span className="text-slate-200">Open this app</span> to switch.
            </span>
          ) : (
            <span className="text-xs text-slate-300">Open the generated app in a new browser tab.</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {ownsRunning ? (
            <button
              type="button"
              onClick={onStop}
              disabled={submitting}
              className="px-3 py-1.5 text-xs font-medium rounded bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
            >
              <Square size={11} />
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={onLaunch}
              disabled={submitting || transitional}
              className="px-3 py-1.5 text-xs font-medium rounded bg-emerald-600 text-white hover:bg-emerald-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
            >
              <Rocket size={11} />
              {someoneElseRunning ? 'Open this app' : status.state === 'error' ? 'Try again' : 'Open app'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
