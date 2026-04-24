import { StatusPill } from './status-pill'
import { StatusStrip } from './status-strip'
import type { OrbitPhase } from '@/lib/types/ui'

interface Props {
  phase: OrbitPhase
  totalTokens: number
  elapsedMs: number
  isReplay?: boolean
  onNewProject?: () => void
}

export function TopBar({ phase, totalTokens, elapsedMs, isReplay, onNewProject }: Props) {
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
      <StatusStrip
        phase={phase.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
        totalTokens={totalTokens}
        elapsedMs={elapsedMs}
      />
      <div className="flex items-center gap-3">
        <StatusPill phase={phase} />
        <button
          onClick={onNewProject}
          className="px-4 py-1.5 text-xs font-medium rounded-lg bg-[#22d3ee] text-[#0f172a] hover:bg-cyan-300 transition-colors"
        >
          New Project
        </button>
      </div>
    </header>
  )
}
