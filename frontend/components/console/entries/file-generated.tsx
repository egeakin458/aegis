import { FileCode } from 'lucide-react'
import type { FileGeneratedEntry } from '@/lib/types/ui'

const ACTION_COLORS = {
  created: 'text-emerald-400',
  updated: 'text-amber-400',
  removed: 'text-amber-400',
}

export function FileGeneratedCard({ entry }: { entry: FileGeneratedEntry }) {
  const actionLabel = entry.action ? entry.action.charAt(0).toUpperCase() + entry.action.slice(1) : null
  const actionColor = entry.action ? ACTION_COLORS[entry.action] : 'text-blue-400'

  return (
    <div className="flex items-center gap-2 py-1 pl-11">
      <FileCode size={13} className={actionColor} />
      {actionLabel && (
        <span className={`text-xs font-medium ${actionColor}`}>{actionLabel}:</span>
      )}
      <span className="text-xs font-mono text-blue-300">{entry.path}</span>
      {entry.language && !entry.action && (
        <span className="text-xs text-slate-600">{entry.language}</span>
      )}
    </div>
  )
}
