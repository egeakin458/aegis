import { Trophy, AlertTriangle } from 'lucide-react'
import { formatTokens, formatElapsed } from '@/lib/utils/format'
import type { SummaryEntry } from '@/lib/types/ui'

export function SummaryCard({ entry, onViewFiles }: { entry: SummaryEntry; onViewFiles?: () => void }) {
  const isPartial = entry.partial === true
  return (
    <div className={`border rounded-lg p-5 my-2 ${isPartial ? 'border-amber-700/50 bg-amber-950/30' : 'border-emerald-700/50 bg-emerald-950/30'}`}>
      <div className="flex items-center gap-2 mb-3">
        {isPartial
          ? <AlertTriangle size={18} className="text-amber-400" />
          : <Trophy size={18} className="text-emerald-400" />}
        <span className={`text-base font-semibold ${isPartial ? 'text-amber-200' : 'text-emerald-200'}`}>
          {isPartial ? 'Built with caveats' : 'Pipeline Complete'}
        </span>
      </div>
      <p className="text-sm text-slate-300 mb-3">
        {isPartial
          ? `${entry.projectName} was partially built. Review cycles were exhausted before all issues were resolved.`
          : `${entry.projectName} is ready.`}
      </p>
      <div className="flex gap-4 text-xs text-slate-400 mb-4">
        <span>{formatTokens(entry.totalTokens)} tokens</span>
        <span>·</span>
        <span>{formatElapsed(entry.durationMs)}</span>
        <span>·</span>
        <span>{entry.fileCount} files generated</span>
      </div>
      <button
        onClick={onViewFiles}
        className={`px-4 py-2 text-sm font-medium rounded-lg text-white transition-colors ${isPartial ? 'bg-amber-700 hover:bg-amber-600' : 'bg-emerald-700 hover:bg-emerald-600'}`}
      >
        View File Tree
      </button>
    </div>
  )
}
