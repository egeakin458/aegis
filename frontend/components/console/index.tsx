'use client'
import { useEffect, useRef } from 'react'
import { AgentStartCard } from './entries/agent-start'
import { AgentCompleteCard } from './entries/agent-complete'
import { MessageCard } from './entries/message'
import { ProgressUpdateLine } from './entries/progress-update'
import { FileGeneratedCard } from './entries/file-generated'
import { ClarificationCard } from './entries/clarification'
import { ConfigFinalizedCard } from './entries/config-finalized'
import { RevisionRequestedCard } from './entries/revision-requested'
import { ErrorCard } from './entries/error-entry'
import { SummaryCard } from './entries/summary'
import type { ConsoleEntry } from '@/lib/types/ui'

interface Props {
  entries: ConsoleEntry[]
  onClarificationSubmit?: (entryId: string, answers: Record<string, string>) => void
  onViewFiles?: () => void
}

export function ConsolePane({ entries, onClarificationSubmit, onViewFiles }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  function renderEntry(entry: ConsoleEntry) {
    switch (entry.type) {
      case 'agent-start': return <AgentStartCard key={entry.id} entry={entry} />
      case 'agent-complete': return <AgentCompleteCard key={entry.id} entry={entry} />
      case 'message': return <MessageCard key={entry.id} entry={entry} />
      case 'progress-update': return <ProgressUpdateLine key={entry.id} entry={entry} />
      case 'file-generated': return <FileGeneratedCard key={entry.id} entry={entry} />
      case 'clarification': return (
        <ClarificationCard
          key={entry.id}
          entry={entry}
          onSubmit={(answers) => onClarificationSubmit?.(entry.id, answers)}
        />
      )
      case 'config-finalized': return <ConfigFinalizedCard key={entry.id} entry={entry} />
      case 'revision-requested': return <RevisionRequestedCard key={entry.id} entry={entry} />
      case 'error-entry': return <ErrorCard key={entry.id} entry={entry} />
      case 'summary': return <SummaryCard key={entry.id} entry={entry} onViewFiles={onViewFiles} />
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4 space-y-1">
      {entries.length === 0 && (
        <p className="text-slate-600 text-sm text-center mt-12">
          Submit the intake form to start the pipeline.
        </p>
      )}
      {entries.map(renderEntry)}
      <div ref={bottomRef} />
    </div>
  )
}
