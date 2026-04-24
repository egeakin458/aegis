import { formatTokens, formatElapsed } from '@/lib/utils/format'

interface Props {
  phase: string
  totalTokens: number
  elapsedMs: number
}

export function StatusStrip({ phase, totalTokens, elapsedMs }: Props) {
  return (
    <div className="flex items-center gap-4 text-xs text-slate-400">
      <span>{phase}</span>
      <span className="text-slate-600">·</span>
      <span>{formatTokens(totalTokens)} tokens</span>
      <span className="text-slate-600">·</span>
      <span>{formatElapsed(elapsedMs)}</span>
    </div>
  )
}
