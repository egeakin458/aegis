import { AgentBadge } from '../agent-badge'
import { TypeIcon } from '../type-icon'
import { formatTokens, formatElapsed } from '@/lib/utils/format'
import type { AgentCompleteEntry } from '@/lib/types/ui'

export function AgentCompleteCard({ entry }: { entry: AgentCompleteEntry }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <AgentBadge agent={entry.agent} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <TypeIcon type="agent-complete" />
          <span className="text-sm text-slate-200">{entry.agentLabel} complete</span>
          <span className="ml-auto text-xs text-slate-500">
            {formatTokens(entry.tokensUsed)} tokens · {formatElapsed(entry.durationMs)}
          </span>
        </div>
        <span className="text-xs text-slate-500">{entry.timestamp}</span>
      </div>
    </div>
  )
}
