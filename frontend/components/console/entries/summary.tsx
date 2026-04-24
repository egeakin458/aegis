import { Trophy } from 'lucide-react'
import { formatTokens, formatElapsed } from '@/lib/utils/format'
import type { SummaryEntry } from '@/lib/types/ui'

export function SummaryCard({ entry, onViewFiles }: { entry: SummaryEntry; onViewFiles?: () => void }) {
  return (
    <div className="border border-emerald-700/50 rounded-lg p-5 my-2 bg-emerald-950/30">
      <div className="flex items-center gap-2 mb-3">
        <Trophy size={18} className="text-emerald-400" />
        <span className="text-base font-semibold text-emerald-200">Pipeline Complete</span>
      </div>
      <p className="text-sm text-slate-300 mb-3">{entry.projectName} is ready.</p>
      <div className="flex gap-4 text-xs text-slate-400 mb-4">
        <span>{formatTokens(entry.totalTokens)} tokens</span>
        <span>·</span>
        <span>{formatElapsed(entry.durationMs)}</span>
        <span>·</span>
        <span>{entry.fileCount} files generated</span>
      </div>
      <button
        onClick={onViewFiles}
        className="px-4 py-2 text-sm font-medium rounded-lg bg-emerald-700 text-white hover:bg-emerald-600 transition-colors"
      >
        View File Tree
      </button>
    </div>
  )
}
