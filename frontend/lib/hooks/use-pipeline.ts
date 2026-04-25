'use client'
import { useReducer, useEffect, useRef, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { openSSE } from '@/lib/api/sse'
import { startPipeline, submitClarification as apiSubmitClarification, getOutput } from '@/lib/api/client'
import { mapEventToEntry } from '@/lib/mappers/events'
import { derivePhase } from '@/lib/mappers/phase'
import type { SSEHandle } from '@/lib/api/sse'
import type { PipelineEvent, CustomerConfig, OutputManifest } from '@/lib/utils/generated/schema'
import type { OrbitPhase, ConsoleEntry, ConnectionState } from '@/lib/types/ui'

interface State {
  runId: string | null
  phase: OrbitPhase
  entries: ConsoleEntry[]
  totalTokens: number
  startTime: string | null
  connectionState: ConnectionState
  isReplay: boolean
  output: OutputManifest | null
  seenEventIds: Set<string>
  lastRevisionType: string | null
}

type Action =
  | { type: 'SET_RUN'; runId: string; isReplay: boolean }
  | { type: 'EVENT'; event: PipelineEvent }
  | { type: 'MARK_CLARIFICATION_SUBMITTED'; entryId: string }
  | { type: 'CONNECTION_CHANGE'; connectionState: ConnectionState }
  | { type: 'OUTPUT_LOADED'; manifest: OutputManifest }
  | { type: 'RESET' }

const INITIAL_STATE: State = {
  runId: null,
  phase: 'idle',
  entries: [],
  totalTokens: 0,
  startTime: null,
  connectionState: 'disconnected',
  isReplay: false,
  output: null,
  seenEventIds: new Set(),
  lastRevisionType: null,
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_RUN':
      return {
        ...INITIAL_STATE,
        runId: action.runId,
        isReplay: action.isReplay,
        seenEventIds: new Set(),
      }

    case 'CONNECTION_CHANGE':
      return { ...state, connectionState: action.connectionState }

    case 'OUTPUT_LOADED':
      return { ...state, output: action.manifest }

    case 'MARK_CLARIFICATION_SUBMITTED':
      return {
        ...state,
        entries: state.entries.map(e =>
          e.id === action.entryId && e.type === 'clarification'
            ? { ...e, submitted: true }
            : e
        ),
      }

    case 'RESET':
      return { ...INITIAL_STATE, seenEventIds: new Set() }

    case 'EVENT': {
      const { event } = action
      if (state.seenEventIds.has(event.event_id)) return state

      const newSeen = new Set(state.seenEventIds)
      newSeen.add(event.event_id)

      const startTime = event.event_type === 'pipeline_started'
        ? event.timestamp
        : state.startTime

      const lastRevisionType =
        event.event_type === 'revision_started'
          ? ((event.data.revision_type as string) ?? state.lastRevisionType)
          : state.lastRevisionType

      const addedTokens = event.tokens_used
        ? event.tokens_used.input_tokens + event.tokens_used.output_tokens
        : 0
      const totalTokens = state.totalTokens + addedTokens

      const phase = derivePhase(state.phase, event, lastRevisionType)

      const entry = mapEventToEntry(event, totalTokens)
      const entries = entry ? [...state.entries, entry] : state.entries

      return {
        ...state,
        seenEventIds: newSeen,
        startTime,
        lastRevisionType,
        totalTokens,
        phase,
        entries,
      }
    }

    default:
      return state
  }
}

export function usePipeline() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE)
  const router = useRouter()
  const searchParams = useSearchParams()
  const sseRef = useRef<SSEHandle | null>(null)
  const runIdRef = useRef<string | null>(null)

  const connectSSE = useCallback((runId: string) => {
    sseRef.current?.close()
    sseRef.current = openSSE(runId, {
      onEvent: (event) => {
        dispatch({ type: 'EVENT', event })

        if (event.event_type === 'pipeline_complete' || event.event_type === 'pipeline_failed') {
          sseRef.current?.close()
        }
        if (event.event_type === 'pipeline_complete') {
          getOutput(runId)
            .then(manifest => dispatch({ type: 'OUTPUT_LOADED', manifest }))
            .catch(console.error)
        }
      },
      onConnectionChange: (connectionState) =>
        dispatch({ type: 'CONNECTION_CHANGE', connectionState }),
    })
  }, [])

  // On mount: hydrate from ?run= URL param (replay case)
  useEffect(() => {
    const runId = searchParams.get('run')
    if (runId && runId !== runIdRef.current) {
      runIdRef.current = runId
      dispatch({ type: 'SET_RUN', runId, isReplay: true })
      connectSSE(runId)
    }
    return () => { sseRef.current?.close() }
  // Only run on mount — searchParams intentionally excluded from deps
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startRun = useCallback(async (config: CustomerConfig) => {
    try {
      const { run_id } = await startPipeline(config)
      runIdRef.current = run_id
      dispatch({ type: 'SET_RUN', runId: run_id, isReplay: false })
      router.push(`?run=${run_id}`, { scroll: false })
      connectSSE(run_id)
    } catch (err) {
      console.error('[usePipeline] startRun failed:', err)
    }
  }, [router, connectSSE])

  const handleClarification = useCallback(async (
    entryId: string,
    answers: Record<string, string>,
  ) => {
    if (!runIdRef.current) return
    dispatch({ type: 'MARK_CLARIFICATION_SUBMITTED', entryId })
    try {
      await apiSubmitClarification(runIdRef.current, answers)
    } catch (err) {
      console.error('[usePipeline] submitClarification failed:', err)
    }
  }, [])

  const resetRun = useCallback(() => {
    sseRef.current?.close()
    sseRef.current = null
    runIdRef.current = null
    dispatch({ type: 'RESET' })
    router.push('/', { scroll: false })
  }, [router])

  return { state, startRun, submitClarification: handleClarification, resetRun }
}
