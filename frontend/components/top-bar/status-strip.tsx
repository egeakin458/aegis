import { formatTokens, formatElapsed } from '@/lib/utils/format'
import { phaseRemainingLabel } from '@/lib/utils/eta'
import type { OrbitPhase } from '@/lib/types/ui'

interface Props {
  totalTokens: number
  elapsedMs: number
  phase: OrbitPhase
}

export function StatusStrip({ totalTokens, elapsedMs, phase }: Props) {
  const eta = phaseRemainingLabel(phase)
  return (
    <div className="flex items-center gap-4 text-xs text-slate-400">
      <span>{formatTokens(totalTokens)} tokens</span>
      <span className="text-slate-600">·</span>
      <span>{formatElapsed(elapsedMs)}</span>
      {eta && (
        <>
          <span className="text-slate-600">·</span>
          <span className="text-slate-500">{eta}</span>
        </>
      )}
    </div>
  )
}
