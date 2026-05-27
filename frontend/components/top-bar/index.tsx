'use client'
import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { StatusPill } from './status-pill'
import { StatusStrip } from './status-strip'
import type { OrbitPhase } from '@/lib/types/ui'

interface Props {
  phase: OrbitPhase
  totalTokens: number
  elapsedMs: number
  isReplay?: boolean
  runId?: string | null
  onNewProject?: () => void
}

const TERMINAL_PHASES: OrbitPhase[] = ['idle', 'complete', 'error']

export function TopBar({ phase, totalTokens, elapsedMs, isReplay, runId, onNewProject }: Props) {
  const [copied, setCopied] = useState(false)

  function copyShareLink() {
    if (!runId || typeof window === 'undefined') return
    const url = `${window.location.origin}${window.location.pathname}?run=${runId}`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  function handleNewProject() {
    const midFlight = !TERMINAL_PHASES.includes(phase)
    if (midFlight) {
      const ok = window.confirm('A pipeline is still running. Start a new project and abandon this run?')
      if (!ok) return
    }
    onNewProject?.()
  }
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-[#0f172a]/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <span className="text-white font-semibold tracking-tight">Aegis</span>
        {isReplay && (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            REPLAY
          </span>
        )}
      </div>
      <StatusStrip totalTokens={totalTokens} elapsedMs={elapsedMs} phase={phase} />
      <div className="flex items-center gap-3">
        <StatusPill phase={phase} />
        {runId && (
          <button
            onClick={copyShareLink}
            title="Copy a link that replays this run"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-slate-100 transition-colors"
          >
            {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
            {copied ? 'Copied' : 'Share link'}
          </button>
        )}
        <button
          onClick={handleNewProject}
          className="px-4 py-1.5 text-xs font-medium rounded-lg bg-[#22d3ee] text-[#0f172a] hover:bg-cyan-300 transition-colors"
        >
          New Project
        </button>
      </div>
    </header>
  )
}
