'use client'
import { useState } from 'react'
import { ChevronDown, ChevronRight, FileCode } from 'lucide-react'
import { AgentBadge } from '../agent-badge'
import { FileGeneratedCard } from './file-generated'
import type { AgentId, FileGeneratedEntry } from '@/lib/types/ui'

interface Props {
  agent: AgentId | 'sys'
  entries: FileGeneratedEntry[]
}

const AGENT_LABELS: Record<AgentId | 'sys', string> = {
  ra: 'Requirements Analyst',
  sa: 'Solution Architect',
  dev: 'Developer',
  qa: 'Quality Reviewer',
  sys: 'Aegis',
}

export function FileGeneratedGroup({ agent, entries }: Props) {
  const [open, setOpen] = useState(false)
  if (entries.length === 1) return <FileGeneratedCard entry={entries[0]} />

  const label = AGENT_LABELS[agent]
  const Chevron = open ? ChevronDown : ChevronRight

  return (
    <div className="my-1">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 py-1 px-2 -ml-1 rounded hover:bg-slate-800/40 transition-colors w-full text-left"
      >
        <AgentBadge agent={agent} />
        <Chevron size={14} className="text-slate-500" />
        <FileCode size={14} className="text-blue-400" />
        <span className="text-xs text-slate-300">
          {label} wrote <span className="font-medium text-blue-300">{entries.length} files</span>
        </span>
      </button>
      {open && (
        <div className="border-l border-slate-800 ml-3 pl-1">
          {entries.map(e => <FileGeneratedCard key={e.id} entry={e} />)}
        </div>
      )}
    </div>
  )
}
