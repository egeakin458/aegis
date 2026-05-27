import type { OrbitPhase } from '@/lib/types/ui'

const REMAINING_SECONDS: Partial<Record<OrbitPhase, number>> = {
  'ra-running': 210,
  'sa-running': 180,
  'dev-running': 90,
  'build-check-running': 50,
  'build-check-failed': 90,
  'qa-running': 40,
  'dev-revising': 60,
  'sa-revising': 90,
}

export function phaseRemainingLabel(phase: OrbitPhase): string | null {
  const s = REMAINING_SECONDS[phase]
  if (!s) return null
  if (s >= 60) {
    const m = Math.round(s / 60)
    return `~${m}m left`
  }
  return `~${s}s left`
}
