'use client'
import { Suspense, useState } from 'react'
import { TopBar } from '@/components/top-bar'
import { AgentOrbit } from '@/components/agent-orbit'
import { ConsolePane } from '@/components/console'
import { IntakeModal } from '@/components/intake-modal'
import { usePipeline } from '@/lib/hooks/use-pipeline'
import { useElapsed } from '@/lib/hooks/use-elapsed'

function PipelineApp() {
  const [modalOpen, setModalOpen] = useState(false)
  const { state, startRun, submitClarification } = usePipeline()
  const frozen = state.phase === 'complete' || state.phase === 'error'
  const elapsedMs = useElapsed(state.startTime, frozen)

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        phase={state.phase}
        totalTokens={state.totalTokens}
        elapsedMs={elapsedMs}
        onNewProject={() => setModalOpen(true)}
      />
      <main className="flex flex-1 overflow-hidden">
        <div className="w-[460px] shrink-0 flex items-center justify-center border-r border-slate-800/50 py-8">
          <AgentOrbit phase={state.phase} />
        </div>
        <div className="flex-1 flex flex-col overflow-hidden">
          <ConsolePane
            entries={state.entries}
            onClarificationSubmit={submitClarification}
          />
        </div>
      </main>
      <IntakeModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={startRun}
      />
    </div>
  )
}

export default function Home() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#0f172a]" />}>
      <PipelineApp />
    </Suspense>
  )
}
