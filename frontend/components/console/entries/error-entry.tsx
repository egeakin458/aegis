import { AgentBadge } from '../agent-badge'
import { TypeIcon } from '../type-icon'
import type { ErrorEntry } from '@/lib/types/ui'

export function ErrorCard({ entry }: { entry: ErrorEntry }) {
  return (
    <div className="border border-red-800/50 rounded-lg p-4 my-2 bg-red-950/20">
      <div className="flex items-center gap-2 mb-2">
        <AgentBadge agent={entry.agent} />
        <TypeIcon type="error-entry" />
        <span className="text-sm font-medium text-red-200">{entry.message}</span>
      </div>
      {entry.detail && (
        <pre className="text-xs text-slate-400 font-mono whitespace-pre-wrap">{entry.detail}</pre>
      )}
      {entry.terminal && (
        <div className="mt-3 flex gap-2">
          <button className="px-3 py-1 text-xs rounded bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors">
            Start Over
          </button>
          <button className="px-3 py-1 text-xs rounded bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors">
            View Logs
          </button>
        </div>
      )}
    </div>
  )
}
