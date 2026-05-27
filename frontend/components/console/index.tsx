'use client'
import { useEffect, useRef } from 'react'
import { AgentStartCard } from './entries/agent-start'
import { AgentCompleteCard } from './entries/agent-complete'
import { MessageCard } from './entries/message'
import { ProgressUpdateLine } from './entries/progress-update'
import { FileGeneratedCard } from './entries/file-generated'
import { FileGeneratedGroup } from './entries/file-generated-group'
import { ClarificationCard } from './entries/clarification'
import { ConfigFinalizedCard } from './entries/config-finalized'
import { ConfigSubmittedCard } from './entries/config-submitted'
import { FlowPrimerCard } from './entries/flow-primer'
import { RevisionRequestedCard } from './entries/revision-requested'
import { BuildCheckCard } from './entries/build-check'
import { ErrorCard } from './entries/error-entry'
import { SummaryCard } from './entries/summary'
import type { ConsoleEntry, FileGeneratedEntry } from '@/lib/types/ui'

type RenderItem =
  | { kind: 'entry'; entry: ConsoleEntry }
  | { kind: 'file-group'; key: string; agent: FileGeneratedEntry['agent']; entries: FileGeneratedEntry[] }

function groupEntries(entries: ConsoleEntry[]): RenderItem[] {
  const items: RenderItem[] = []
  let buf: FileGeneratedEntry[] = []
  const flush = () => {
    if (!buf.length) return
    items.push({ kind: 'file-group', key: `fg-${buf[0].id}`, agent: buf[0].agent, entries: buf })
    buf = []
  }
  for (const e of entries) {
    if (e.type === 'file-generated' && (buf.length === 0 || buf[0].agent === e.agent)) {
      buf.push(e)
    } else {
      flush()
      if (e.type === 'file-generated') buf.push(e)
      else items.push({ kind: 'entry', entry: e })
    }
  }
  flush()
  return items
}

interface Props {
  entries: ConsoleEntry[]
  onClarificationSubmit?: (entryId: string, answers: Record<string, string>) => void
  onViewFiles?: () => void
  onStartOver?: () => void
}

export function ConsolePane({ entries, onClarificationSubmit, onViewFiles, onStartOver }: Props) {
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
      case 'config-submitted': return <ConfigSubmittedCard key={entry.id} entry={entry} />
      case 'flow-primer': return <FlowPrimerCard key={entry.id} />
      case 'revision-requested': return <RevisionRequestedCard key={entry.id} entry={entry} />
      case 'build-check': return <BuildCheckCard key={entry.id} entry={entry} />
      case 'error-entry': return <ErrorCard key={entry.id} entry={entry} onStartOver={onStartOver} />
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
      {groupEntries(entries).map(item =>
        item.kind === 'file-group'
          ? <FileGeneratedGroup key={item.key} agent={item.agent} entries={item.entries} />
          : renderEntry(item.entry)
      )}
      <div ref={bottomRef} />
    </div>
  )
}
