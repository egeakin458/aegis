import { AgentBadge } from '../agent-badge'
import type { ConfigSubmittedEntry } from '@/lib/types/ui'

export function ConfigSubmittedCard({ entry }: { entry: ConfigSubmittedEntry }) {
  return (
    <div className="border border-cyan-900/40 rounded-lg p-4 my-2 bg-cyan-950/10">
      <div className="flex items-center gap-2 mb-2">
        <AgentBadge agent="sys" />
        <span className="text-sm font-medium text-cyan-200">You submitted</span>
        <span className="text-xs text-slate-500 font-mono">{entry.projectName}</span>
      </div>
      <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">{entry.description}</p>
    </div>
  )
}
