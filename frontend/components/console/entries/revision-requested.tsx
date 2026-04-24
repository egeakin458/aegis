'use client'
import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { AgentBadge } from '../agent-badge'
import { TypeIcon } from '../type-icon'
import type { RevisionRequestedEntry } from '@/lib/types/ui'

export function RevisionRequestedCard({ entry }: { entry: RevisionRequestedEntry }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-amber-800/50 rounded-lg p-4 my-2 bg-amber-950/20">
      <div className="flex items-center gap-2 mb-2">
        <AgentBadge agent="qa" />
        <TypeIcon type="revision-requested" />
        <span className="text-sm font-medium text-amber-200">Revision #{entry.revisionNumber} requested</span>
        <span className="ml-auto text-xs text-amber-400">{entry.verdict}</span>
      </div>
      <div className="space-y-1 mb-2">
        {entry.issues.slice(0, expanded ? undefined : 2).map((issue, i) => (
          <p key={i} className="text-xs text-slate-300 flex gap-1.5">
            <span className="text-amber-500">!</span>{issue}
          </p>
        ))}
      </div>
      {entry.issues.length > 2 && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {expanded ? 'Show less' : `${entry.issues.length - 2} more issues`}
        </button>
      )}
    </div>
  )
}
