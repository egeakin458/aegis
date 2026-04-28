import { AgentBadge } from '../agent-badge'
import type { MessageEntry } from '@/lib/types/ui'

export function MessageCard({ entry }: { entry: MessageEntry }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <AgentBadge agent={entry.agent} />
      <p className="text-sm text-slate-300 leading-relaxed">{entry.text}</p>
    </div>
  )
}
