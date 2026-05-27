import { Trophy, AlertTriangle, Check, X } from 'lucide-react'
import { formatTokens, formatElapsed } from '@/lib/utils/format'
import type { SummaryEntry } from '@/lib/types/ui'

export function SummaryCard({ entry, onViewFiles }: { entry: SummaryEntry; onViewFiles?: () => void }) {
  const isPartial = entry.partial === true
  const features = entry.featureStatus ?? []
  const working = features.filter(f => f.implemented)
  const broken = features.filter(f => !f.implemented)

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

      {features.length > 0 && (
        <div className="mb-4 space-y-2">
          {working.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <Check size={12} className="text-emerald-400" />
                <span className="text-xs font-medium text-emerald-300">
                  Working ({working.length})
                </span>
              </div>
              <ul className="ml-5 space-y-0.5">
                {working.map((f, i) => (
                  <li key={i} className="text-xs text-slate-300">{f.name}</li>
                ))}
              </ul>
            </div>
          )}
          {broken.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <X size={12} className="text-red-400" />
                <span className="text-xs font-medium text-red-300">
                  Not working ({broken.length})
                </span>
              </div>
              <ul className="ml-5 space-y-0.5">
                {broken.map((f, i) => (
                  <li key={i} className="text-xs text-slate-300">
                    {f.name}
                    {f.evidence && <span className="text-slate-500"> — {f.evidence}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <button
        onClick={onViewFiles}
        className={`px-4 py-2 text-sm font-medium rounded-lg text-white transition-colors ${isPartial ? 'bg-amber-700 hover:bg-amber-600' : 'bg-emerald-700 hover:bg-emerald-600'}`}
      >
        View File Tree
      </button>
    </div>
  )
}
