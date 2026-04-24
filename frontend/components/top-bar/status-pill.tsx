'use client'
import { cn } from '@/lib/utils'
import type { OrbitPhase } from '@/lib/types/ui'

const PHASE_LABELS: Record<OrbitPhase, string> = {
  idle: 'Ready',
  'ra-running': 'Analyzing Requirements',
  'ra-clarification': 'Waiting for Clarification',
  'sa-running': 'Designing Architecture',
  'dev-running': 'Building Application',
  'qa-running': 'Reviewing Quality',
  'dev-revising': 'Revising Code',
  'sa-revising': 'Revising Design',
  complete: 'Complete',
  error: 'Error',
}

const PHASE_COLORS: Record<OrbitPhase, string> = {
  idle: 'bg-slate-700 text-slate-300',
  'ra-running': 'bg-cyan-900/40 text-cyan-300 border border-cyan-800',
  'ra-clarification': 'bg-amber-900/40 text-amber-300 border border-amber-800',
  'sa-running': 'bg-cyan-900/40 text-cyan-300 border border-cyan-800',
  'dev-running': 'bg-cyan-900/40 text-cyan-300 border border-cyan-800',
  'qa-running': 'bg-cyan-900/40 text-cyan-300 border border-cyan-800',
  'dev-revising': 'bg-amber-900/40 text-amber-300 border border-amber-800',
  'sa-revising': 'bg-amber-900/40 text-amber-300 border border-amber-800',
  complete: 'bg-emerald-900/40 text-emerald-300 border border-emerald-800',
  error: 'bg-red-900/40 text-red-300 border border-red-800',
}

export function StatusPill({ phase }: { phase: OrbitPhase }) {
  return (
    <span className={cn('px-3 py-1 rounded-full text-xs font-medium', PHASE_COLORS[phase])}>
      {PHASE_LABELS[phase]}
    </span>
  )
}
