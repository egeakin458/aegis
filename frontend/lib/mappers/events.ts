import type { PipelineEvent } from '@/lib/types/api'
import type { ConsoleEntry, AgentId } from '@/lib/types/ui'

const AGENT_ID_MAP: Record<string, AgentId | 'sys'> = {
  requirements_analyst: 'ra',
  solution_architect: 'sa',
  developer: 'dev',
  qa_reviewer: 'qa',
  system: 'sys',
}

const AGENT_LABEL_MAP: Record<string, string> = {
  requirements_analyst: 'Requirements Analyst',
  solution_architect: 'Solution Architect',
  developer: 'Developer',
  qa_reviewer: 'QA Reviewer',
  system: 'System',
}

function toAgentId(agent: string): AgentId | 'sys' {
  return AGENT_ID_MAP[agent] ?? 'sys'
}

function toTimestamp(isoString: string): string {
  return new Date(isoString).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function mapEventToEntry(event: PipelineEvent, stateTotalTokens = 0): ConsoleEntry | null {
  const id = event.event_id
  const agent = toAgentId(event.agent)
  const timestamp = toTimestamp(event.timestamp)
  const d = event.data

  switch (event.event_type) {
    case 'agent_start':
      return {
        id, type: 'agent-start', agent, timestamp,
        agentLabel: AGENT_LABEL_MAP[event.agent] ?? event.agent,
      }

    case 'agent_complete': {
      const added = (event.tokens_used?.input_tokens ?? 0) + (event.tokens_used?.output_tokens ?? 0)
      return {
        id, type: 'agent-complete', agent, timestamp,
        agentLabel: AGENT_LABEL_MAP[event.agent] ?? event.agent,
        tokensUsed: added,
        durationMs: event.duration_ms ?? 0,
      }
    }

    case 'clarification_needed': {
      const raw = d.questions as Array<{ id: string; question: string }> | undefined
      const questions = (raw ?? []).map(q => ({ id: q.id, question: q.question }))
      return { id, type: 'clarification', agent, timestamp, questions, submitted: false }
    }

    case 'config_finalized':
      return {
        id, type: 'config-finalized', agent, timestamp,
        projectSummary: (d.project_summary as string) ?? event.message,
        assumptions: [],
      }

    case 'revision_requested':
      return {
        id, type: 'revision-requested', agent, timestamp,
        verdict: (d.verdict as string) ?? '',
        issues: (d.issues as string[]) ?? [],
        revisionNumber: (d.revision_number as number) ?? 1,
        expanded: false,
      }

    case 'revision_started':
      return { id, type: 'message', agent, timestamp, text: event.message }

    case 'file_generated':
      return {
        id, type: 'file-generated', agent, timestamp,
        path: (d.path as string) ?? '',
        language: (d.language as string) ?? '',
      }

    case 'progress_update':
      return { id, type: 'progress-update', agent, timestamp, text: event.message }

    case 'validation_failed':
      return {
        id, type: 'error-entry', agent, timestamp,
        message: event.message,
        detail: (d.error as string) ?? undefined,
        terminal: false,
      }

    case 'error':
      return {
        id, type: 'error-entry', agent, timestamp,
        message: event.message,
        detail: (d.error as string) ?? undefined,
        terminal: false,
      }

    case 'pipeline_failed':
      return {
        id, type: 'error-entry', agent, timestamp,
        message: event.message,
        detail: (d.error as string) ?? undefined,
        terminal: true,
      }

    case 'pipeline_complete':
      return {
        id, type: 'summary', agent, timestamp,
        projectName: 'Your Application',
        totalTokens: stateTotalTokens,
        durationMs: 0,
        fileCount: 0,
      }

    // Intentionally ignored event types
    case 'pipeline_started':
    case 'llm_call_start':
    case 'llm_call_complete':
    case 'clarification_received':
    case 'validation_passed':
      return null

    default:
      return null
  }
}
