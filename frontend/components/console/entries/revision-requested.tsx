'use client'
import { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp, FileText, Lightbulb } from 'lucide-react'
import { AgentBadge } from '../agent-badge'
import type { IssueSeverity, ReviewIssue, RevisionRequestedEntry } from '@/lib/types/ui'

const SEVERITY_ORDER: IssueSeverity[] = ['critical', 'major', 'minor', 'suggestion']

const SEVERITY_LABEL: Record<IssueSeverity, string> = {
  critical: 'Critical',
  major: 'Major',
  minor: 'Minor',
  suggestion: 'Suggestion',
}

// Critical code issues get a red tag inline because they describe real
// problems in the generated code (not pipeline failure — the agents
// will fix them, but they ARE serious). Everything else is amber-graded.
const SEVERITY_STYLES: Record<IssueSeverity, string> = {
  critical: 'bg-red-950/40 text-red-300 border-red-800/60',
  major:    'bg-amber-950/40 text-amber-300 border-amber-800/60',
  minor:    'bg-amber-900/30 text-amber-200 border-amber-800/40',
  suggestion: 'bg-slate-800/60 text-slate-300 border-slate-700',
}

const VERDICT_LABEL = {
  revise_code: 'Code revision',
  revise_design: 'Design revision',
} as const

function QualityDots({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">Code quality</span>
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map(n => (
          <span
            key={n}
            className={`inline-block w-1.5 h-1.5 rounded-full ${
              n <= score ? 'bg-amber-400' : 'bg-slate-700'
            }`}
          />
        ))}
      </div>
      <span className="text-[10px] text-slate-500">{score}/5</span>
    </div>
  )
}

function IssueRow({ issue, showSuggestions }: { issue: ReviewIssue; showSuggestions: boolean }) {
  return (
    <div className="py-1.5">
      <div className="flex items-start gap-2">
        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${SEVERITY_STYLES[issue.severity]} shrink-0 mt-0.5`}>
          {SEVERITY_LABEL[issue.severity]}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-slate-200 leading-snug">{issue.description}</p>
          {issue.affectedFile && (
            <p className="flex items-center gap-1 mt-0.5 text-[11px] text-blue-300 font-mono">
              <FileText size={10} className="text-slate-500 shrink-0" />
              <span className="truncate">{issue.affectedFile}</span>
            </p>
          )}
          {showSuggestions && issue.suggestion && (
            <p className="flex items-start gap-1 mt-1 text-[11px] text-slate-400 leading-snug">
              <Lightbulb size={11} className="text-amber-400/70 shrink-0 mt-0.5" />
              <span><span className="text-amber-400/80">Suggestion:</span> {issue.suggestion}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export function RevisionRequestedCard({ entry }: { entry: RevisionRequestedEntry }) {
  const [expanded, setExpanded] = useState(false)

  // Group + sort issues by severity (critical first)
  const grouped = SEVERITY_ORDER
    .map(sev => ({ severity: sev, items: entry.issues.filter(i => i.severity === sev) }))
    .filter(g => g.items.length > 0)

  const hasSuggestions = entry.issues.some(i => !!i.suggestion)

  return (
    <div className="border border-amber-800/50 rounded-lg p-4 my-2 bg-amber-950/20">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <AgentBadge agent="qa" />
        <AlertTriangle size={16} className="text-amber-400" />
        <span className="text-sm font-medium text-amber-200">Reviewer requested revision</span>
        <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-amber-900/40 text-amber-300 border border-amber-800/60">
          {VERDICT_LABEL[entry.verdict]}
        </span>
        <span className="ml-auto text-[11px] text-slate-400 font-medium">
          Round {entry.revisionNumber} of {entry.revisionMax}
        </span>
      </div>

      {/* Quality + summary */}
      <div className="mb-3 flex flex-wrap items-start gap-x-4 gap-y-2">
        <QualityDots score={entry.codeQualityScore} />
      </div>
      {entry.summary && (
        <p className="text-xs text-slate-300 leading-snug mb-2">{entry.summary}</p>
      )}

      {/* Issues grouped by severity */}
      {grouped.length > 0 && (
        <div className="space-y-2 mt-2">
          {grouped.map(group => (
            <div key={group.severity}>
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">
                {SEVERITY_LABEL[group.severity]} · {group.items.length}
              </div>
              <div className="border-l border-amber-800/30 pl-2 divide-y divide-slate-800/40">
                {group.items.map((issue, i) => (
                  <IssueRow key={issue.id ?? i} issue={issue} showSuggestions={expanded} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Expand suggestions toggle */}
      {hasSuggestions && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1 mt-3 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {expanded ? 'Hide suggestions' : 'Show suggestions'}
        </button>
      )}

      {/* Footer reassurance */}
      <p className="text-xs text-slate-400 mt-3 italic">
        The agents will address these and try again — no action needed on your side.
      </p>
    </div>
  )
}
