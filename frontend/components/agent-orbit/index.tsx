'use client'
import { AgentNode } from './agent-node'
import { OrbitArcs } from './arcs'
import { CenterPanel } from './center-panel'
import type { AgentId, OrbitPhase } from '@/lib/types/ui'

const CANVAS = 560
const C = 280
const R = 190

// Agents placed at cardinal positions
const NODE_POSITIONS: Record<AgentId, { x: number; y: number }> = {
  ra:  { x: C,     y: C - R },  // top
  sa:  { x: C + R, y: C },      // right
  dev: { x: C,     y: C + R },  // bottom
  qa:  { x: C - R, y: C },      // left
}

type NodeState = 'idle' | 'active' | 'waiting' | 'complete' | 'error'

function deriveNodeStates(phase: OrbitPhase): Record<AgentId, NodeState> {
  const all: Record<AgentId, NodeState> = { ra: 'idle', sa: 'idle', dev: 'idle', qa: 'idle' }
  switch (phase) {
    case 'ra-running': return { ...all, ra: 'active' }
    case 'ra-clarification': return { ...all, ra: 'waiting' }
    case 'sa-running': return { ...all, ra: 'complete', sa: 'active' }
    case 'dev-running': return { ...all, ra: 'complete', sa: 'complete', dev: 'active' }
    case 'qa-running': return { ...all, ra: 'complete', sa: 'complete', dev: 'complete', qa: 'active' }
    case 'dev-revising': return { ...all, ra: 'complete', sa: 'complete', dev: 'active', qa: 'waiting' }
    case 'sa-revising': return { ...all, ra: 'complete', sa: 'active', dev: 'idle', qa: 'waiting' }
    case 'complete': return { ra: 'complete', sa: 'complete', dev: 'complete', qa: 'complete' }
    case 'error': return { ...all }
    default: return all
  }
}

function deriveActiveArc(phase: OrbitPhase): number | null {
  switch (phase) {
    case 'ra-running': case 'ra-clarification': return 0
    case 'sa-running': return 1
    case 'dev-running': case 'dev-revising': return 2
    case 'qa-running': return 3
    default: return null
  }
}

export function AgentOrbit({ phase }: { phase: OrbitPhase }) {
  const nodeStates = deriveNodeStates(phase)
  const activeArc = deriveActiveArc(phase)

  return (
    <div className="flex items-center justify-center">
      <svg width={CANVAS} height={CANVAS} viewBox={`0 0 ${CANVAS} ${CANVAS}`}>
        <OrbitArcs cx={C} cy={C} r={R} activeSegment={activeArc} />
        {(Object.entries(NODE_POSITIONS) as [AgentId, { x: number; y: number }][]).map(([agent, pos]) => (
          <AgentNode key={agent} agent={agent} state={nodeStates[agent]} x={pos.x} y={pos.y} />
        ))}
        <CenterPanel phase={phase} cx={C} cy={C} />
      </svg>
    </div>
  )
}
