'use client'
import { Suspense, useState, useEffect } from 'react'
import { TopBar } from '@/components/top-bar'
import { AgentOrbit } from '@/components/agent-orbit'
import { ConsolePane } from '@/components/console'
import { IntakeModal } from '@/components/intake-modal'
import { OutputViewer } from '@/components/output-viewer'
import { ConnectionLostPill } from '@/components/connection-lost-pill'
import { usePipeline } from '@/lib/hooks/use-pipeline'
import { useElapsed } from '@/lib/hooks/use-elapsed'
import { useTokenCounter } from '@/lib/hooks/use-token-counter'

function PipelineApp() {
  const [modalOpen, setModalOpen] = useState(false)
  const [viewerOpen, setViewerOpen] = useState(false)
  const { state, startRun, submitClarification, resetRun } = usePipeline()
  const frozen = state.phase === 'complete' || state.phase === 'error'
  const elapsedMs = useElapsed(state.startTime, frozen)
  const displayTokens = useTokenCounter(state.totalTokens)

  // Keyboard shortcuts: Esc closes modals, Cmd/Ctrl+K opens intake
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setModalOpen(false)
        setViewerOpen(false)
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setModalOpen(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        phase={state.phase}
        totalTokens={displayTokens}
        elapsedMs={elapsedMs}
        isReplay={state.isReplay}
        onNewProject={() => setModalOpen(true)}
        onStartOver={resetRun}
      />
      {/* Responsive: stacks vertically below lg (1024px), side-by-side above */}
      <main className="flex flex-1 overflow-hidden flex-col lg:flex-row">
        <div className="lg:w-[460px] lg:shrink-0 flex items-center justify-center border-b lg:border-b-0 lg:border-r border-slate-800/50 py-8">
          <AgentOrbit phase={state.phase} />
        </div>
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          <ConsolePane
            entries={state.entries}
            onClarificationSubmit={submitClarification}
            onViewFiles={() => setViewerOpen(true)}
          />
        </div>
      </main>
      <IntakeModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={startRun}
      />
      <OutputViewer
        manifest={state.output}
        runId={state.runId}
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
      />
      <ConnectionLostPill state={state.connectionState} />
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
