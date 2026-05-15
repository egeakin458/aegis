import { AlertTriangle, XCircle } from 'lucide-react'
import { AgentBadge } from '../agent-badge'
import type { ErrorEntry } from '@/lib/types/ui'

interface Props {
  entry: ErrorEntry
  onStartOver?: () => void
}

export function ErrorCard({ entry, onStartOver }: Props) {
  const isTerminal = entry.terminal

  const palette = isTerminal
    ? { border: 'border-red-800/50', bg: 'bg-red-950/20', text: 'text-red-200', icon: 'text-red-400' }
    : { border: 'border-amber-800/50', bg: 'bg-amber-950/20', text: 'text-amber-200', icon: 'text-amber-400' }

  const Icon = isTerminal ? XCircle : AlertTriangle

  return (
    <div className={`border ${palette.border} rounded-lg p-4 my-2 ${palette.bg}`}>
      <div className="flex items-center gap-2 mb-2">
        <AgentBadge agent={entry.agent} />
        <Icon size={16} className={palette.icon} />
        <span className={`text-sm font-medium ${palette.text}`}>{entry.message}</span>
      </div>
      {entry.detail && isTerminal && (
        <pre className="text-xs text-slate-400 font-mono whitespace-pre-wrap">{entry.detail}</pre>
      )}
      {isTerminal && onStartOver && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={onStartOver}
            className="px-3 py-1 text-xs rounded bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
          >
            Start Over
          </button>
        </div>
      )}
    </div>
  )
}
