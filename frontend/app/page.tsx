'use client'
import { Suspense, useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
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
  const searchParams = useSearchParams()
  const [modalOpen, setModalOpen] = useState(() => !searchParams.get('run'))
  const [viewerOpen, setViewerOpen] = useState(false)
  const { state, startRun, submitClarification, resetRun, reconnect } = usePipeline()
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
        runId={state.runId}
        onNewProject={() => {
          resetRun()
          setModalOpen(true)
        }}
      />
      {/* Responsive: stacks vertically below lg (1024px), side-by-side above */}
      <main className="flex flex-1 overflow-hidden flex-col lg:flex-row">
        <div
          className="lg:flex-[0_0_560px] flex items-center justify-center border-b lg:border-b-0 lg:border-r border-transparent py-8"
          style={{ background: 'radial-gradient(ellipse at center, rgba(34,211,238,0.05) 0%, transparent 70%)' }}
        >
          <AgentOrbit phase={state.phase} />
        </div>
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          <ConsolePane
            entries={state.entries}
            onClarificationSubmit={submitClarification}
            onViewFiles={() => setViewerOpen(true)}
            onStartOver={resetRun}
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
      <ConnectionLostPill state={state.connectionState} hasRun={state.runId !== null} onReconnect={reconnect} />
    </div>
  )
}

function PipelineFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0f172a]">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
        Loading Aegis…
      </div>
    </div>
  )
}

export default function Home() {
  return (
    <Suspense fallback={<PipelineFallback />}>
      <PipelineApp />
    </Suspense>
  )
}
