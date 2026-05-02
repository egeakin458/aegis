import type { BuildCheckEntry } from '@/lib/types/ui'

export function BuildCheckCard({ entry }: { entry: BuildCheckEntry }) {
  const errorCount = entry.issues.filter(i => i.severity === 'error').length
  const warnCount = entry.issues.filter(i => i.severity === 'warning').length

  return (
    <div className={`border rounded-lg p-4 my-2 ${
      entry.passed
        ? 'border-emerald-800/50 bg-emerald-950/20'
        : 'border-red-800/50 bg-red-950/20'
    }`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-xs font-semibold uppercase tracking-wide ${
          entry.passed ? 'text-emerald-400' : 'text-red-400'
        }`}>
          {entry.passed ? '✓ Build Check Passed' : '✗ Build Check Failed'}
        </span>
        <span className="text-xs text-slate-500 ml-auto">
          {entry.filesChecked} files · {entry.durationMs}ms
        </span>
      </div>

      {!entry.passed && (errorCount > 0 || warnCount > 0) && (
        <div className="text-xs text-slate-400 mb-2">
          {errorCount > 0 && <span className="text-red-400">{errorCount} error{errorCount !== 1 ? 's' : ''}</span>}
          {errorCount > 0 && warnCount > 0 && <span> · </span>}
          {warnCount > 0 && <span className="text-amber-400">{warnCount} warning{warnCount !== 1 ? 's' : ''}</span>}
        </div>
      )}

      {entry.issues.length > 0 && (
        <ul className="space-y-1 mt-2">
          {entry.issues.map((issue, i) => (
            <li key={i} className="font-mono text-xs text-slate-300">
              <span className={issue.severity === 'error' ? 'text-red-400' : 'text-amber-400'}>
                {issue.severity.toUpperCase()}
              </span>
              {' '}
              <span className="text-slate-400">{issue.file}</span>
              {issue.line != null && <span className="text-slate-500">:{issue.line}</span>}
              {issue.column != null && <span className="text-slate-500">:{issue.column}</span>}
              {' — '}
              {issue.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
