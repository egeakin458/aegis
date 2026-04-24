'use client'
import { useState } from 'react'
import { AgentBadge } from '../agent-badge'
import { TypeIcon } from '../type-icon'
import type { ClarificationEntry } from '@/lib/types/ui'

interface Props {
  entry: ClarificationEntry
  onSubmit?: (answers: Record<string, string>) => void
}

export function ClarificationCard({ entry, onSubmit }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>({})

  const allAnswered = entry.questions.every(q => answers[q.id]?.trim())

  return (
    <div className="border border-amber-800/50 rounded-lg p-4 my-2 bg-amber-950/20">
      <div className="flex items-center gap-2 mb-3">
        <AgentBadge agent="ra" />
        <TypeIcon type="clarification" />
        <span className="text-sm font-medium text-amber-200">Clarification needed</span>
      </div>
      <div className="space-y-3">
        {entry.questions.map((q, i) => (
          <div key={q.id}>
            <p className="text-xs text-slate-300 mb-1">{i + 1}. {q.question}</p>
            {entry.submitted ? (
              <p className="text-xs text-slate-400 italic">{q.answer ?? answers[q.id]}</p>
            ) : (
              <textarea
                className="w-full text-xs bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-200 resize-none focus:outline-none focus:border-amber-600"
                rows={2}
                value={answers[q.id] ?? ''}
                onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                placeholder="Your answer..."
              />
            )}
          </div>
        ))}
      </div>
      {!entry.submitted && (
        <button
          disabled={!allAnswered}
          onClick={() => onSubmit?.(answers)}
          className="mt-3 px-4 py-1.5 text-xs font-medium rounded bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Submit Answers
        </button>
      )}
    </div>
  )
}
