import { AgentBadge } from '../agent-badge'
import { TypeIcon } from '../type-icon'
import type { AgentStartEntry } from '@/lib/types/ui'

export function AgentStartCard({ entry }: { entry: AgentStartEntry }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <AgentBadge agent={entry.agent} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <TypeIcon type="agent-start" />
          <span className="text-sm text-slate-200">{entry.agentLabel} started</span>
        </div>
        <span className="text-xs text-slate-500">{entry.timestamp}</span>
      </div>
    </div>
  )
}
