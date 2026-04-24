import type { OrbitPhase } from '@/lib/types/ui'

const MESSAGES: Record<OrbitPhase, { title: string; sub: string }> = {
  idle: { title: 'Ready', sub: 'Submit the intake form to begin' },
  'ra-running': { title: 'Analyzing', sub: 'Requirements Analyst is working' },
  'ra-clarification': { title: 'Waiting', sub: 'Clarification needed' },
  'sa-running': { title: 'Designing', sub: 'Solution Architect is working' },
  'dev-running': { title: 'Building', sub: 'Developer is writing code' },
  'qa-running': { title: 'Reviewing', sub: 'QA Reviewer is checking quality' },
  'dev-revising': { title: 'Revising', sub: 'Developer updating code' },
  'sa-revising': { title: 'Revising', sub: 'Architect updating design' },
  complete: { title: 'Complete', sub: 'Your application is ready' },
  error: { title: 'Error', sub: 'Something went wrong' },
}

export function CenterPanel({ phase, cx, cy }: { phase: OrbitPhase; cx: number; cy: number }) {
  const { title, sub } = MESSAGES[phase]
  return (
    <g>
      <text x={cx} y={cy - 8} textAnchor="middle" fontSize={14} fontWeight={700} fill="#f1f5f9">{title}</text>
      <text x={cx} y={cy + 10} textAnchor="middle" fontSize={9} fill="#64748b">{sub}</text>
    </g>
  )
}
