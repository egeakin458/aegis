import type { PipelineEvent } from '@/lib/utils/generated/schema'
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

    case 'pipeline_complete': return 'complete'
    case 'pipeline_failed': return 'error'

    default: return current
  }
}
