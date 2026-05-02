import type { PipelineEvent } from '@/lib/types/api'
import type { OrbitPhase } from '@/lib/types/ui'

export function derivePhase(
  current: OrbitPhase,
  event: PipelineEvent,
  lastRevisionType: string | null,
): OrbitPhase {
  switch (event.event_type) {
    case 'pipeline_started':
      return 'idle'

    case 'agent_start':
      switch (event.agent) {
        case 'requirements_analyst': return 'ra-running'
        case 'solution_architect':
          return lastRevisionType === 'design' ? 'sa-revising' : 'sa-running'
        case 'developer':
          return lastRevisionType === 'code' ? 'dev-revising' : 'dev-running'
        case 'qa_reviewer': return 'qa-running'
        default: return current
      }

    case 'clarification_needed': return 'ra-clarification'
    case 'clarification_received': return 'ra-running'

    case 'build_check_start': return 'build-check-running'
    case 'build_check_complete': return 'build-check-running'
    case 'build_check_failed': return 'build-check-failed'

    case 'pipeline_complete': return 'complete'
    case 'pipeline_partial': return 'complete'
    case 'pipeline_failed': return 'error'

    default: return current
  }
}
