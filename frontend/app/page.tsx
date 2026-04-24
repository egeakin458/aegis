'use client'
import { useState } from 'react'
import { TopBar } from '@/components/top-bar'
import { AgentOrbit } from '@/components/agent-orbit'
import { ConsolePane } from '@/components/console'
import { IntakeModal } from '@/components/intake-modal'
import type { OrbitPhase, ConsoleEntry } from '@/lib/types/ui'

const SAMPLE_ENTRIES: ConsoleEntry[] = [
  { id: '1', type: 'agent-start', agent: 'ra', agentLabel: 'Requirements Analyst', timestamp: '10:00:01' },
  { id: '2', type: 'progress-update', agent: 'ra', text: 'Analyzing business context...', timestamp: '10:00:02' },
  { id: '3', type: 'config-finalized', agent: 'ra', projectSummary: 'A retail inventory management system for small businesses.', assumptions: ['Web-based, mobile-responsive', 'SQLite database', 'Up to 1000 products'], timestamp: '10:00:10' },
  { id: '4', type: 'agent-complete', agent: 'ra', agentLabel: 'Requirements Analyst', tokensUsed: 2800, durationMs: 9000, timestamp: '10:00:10' },
  { id: '5', type: 'agent-start', agent: 'sa', agentLabel: 'Solution Architect', timestamp: '10:00:11' },
]

export default function Home() {
  const [phase] = useState<OrbitPhase>('sa-running')
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        phase={phase}
        totalTokens={2800}
        elapsedMs={11000}
        onNewProject={() => setModalOpen(true)}
      />
      <main className="flex flex-1 overflow-hidden">
        {/* Left: Orbit */}
        <div className="w-[460px] shrink-0 flex items-center justify-center border-r border-slate-800/50 py-8">
          <AgentOrbit phase={phase} />
        </div>
        {/* Right: Console */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <ConsolePane entries={SAMPLE_ENTRIES} />
        </div>
      </main>
      <IntakeModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}
