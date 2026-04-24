import { AgentBadge } from '../agent-badge'
import { TypeIcon } from '../type-icon'
import type { ConfigFinalizedEntry } from '@/lib/types/ui'

export function ConfigFinalizedCard({ entry }: { entry: ConfigFinalizedEntry }) {
  return (
    <div className="border border-emerald-800/50 rounded-lg p-4 my-2 bg-emerald-950/20">
      <div className="flex items-center gap-2 mb-2">
        <AgentBadge agent="ra" />
        <TypeIcon type="config-finalized" />
        <span className="text-sm font-medium text-emerald-200">Requirements finalized</span>
      </div>
      <p className="text-xs text-slate-300 mb-2">{entry.projectSummary}</p>
      {entry.assumptions.length > 0 && (
        <ul className="space-y-1">
          {entry.assumptions.map((a, i) => (
            <li key={i} className="text-xs text-slate-400 flex gap-1.5">
              <span className="text-emerald-600">·</span>{a}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
