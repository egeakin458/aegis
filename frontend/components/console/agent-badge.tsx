import { cn } from '@/lib/utils'
import type { AgentId } from '@/lib/types/ui'

const MONOGRAMS: Record<AgentId | 'sys', string> = {
  ra: 'RA', sa: 'SA', dev: 'DE', qa: 'QA', sys: 'SY',
}
const COLORS: Record<AgentId | 'sys', string> = {
  ra: 'bg-cyan-900 text-cyan-300',
  sa: 'bg-violet-900 text-violet-300',
  dev: 'bg-blue-900 text-blue-300',
  qa: 'bg-emerald-900 text-emerald-300',
  sys: 'bg-slate-800 text-slate-400',
}

export function AgentBadge({ agent, size = 'md' }: { agent: AgentId | 'sys'; size?: 'sm' | 'md' }) {
  return (
    <span className={cn(
      'inline-flex items-center justify-center rounded font-mono font-bold select-none',
      size === 'sm' ? 'w-6 h-6 text-[10px]' : 'w-8 h-8 text-xs',
      COLORS[agent]
    )}>
      {MONOGRAMS[agent]}
    </span>
  )
}
