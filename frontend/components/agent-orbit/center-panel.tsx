'use client'
import { AnimatePresence, motion } from 'framer-motion'
import type { OrbitPhase } from '@/lib/types/ui'

const MESSAGES: Record<OrbitPhase, { title: string; sub: string }> = {
  idle: { title: 'Ready', sub: 'Submit the intake form to begin' },
  'ra-running': { title: 'Analyzing', sub: 'Requirements Analyst is working' },
  'ra-clarification': { title: 'Waiting', sub: 'Clarification needed' },
  'sa-running': { title: 'Designing', sub: 'Solution Architect is working' },
  'dev-running': { title: 'Building', sub: 'Developer is writing code' },
  'build-check-running': { title: 'Checking', sub: 'Verifying code structure' },
  'build-check-failed': { title: 'Fixing', sub: 'Build errors found — revising' },
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
      <circle r={65} cx={cx} cy={cy} fill="rgba(15,23,42,0.75)" stroke="#1e3a4a" strokeWidth={1} />
      <foreignObject x={cx - 75} y={cy - 32} width={150} height={64}>
        <AnimatePresence mode="wait">
          <motion.div
            key={phase}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25 }}
            style={{ textAlign: 'center', fontFamily: 'inherit' }}
          >
            <div style={{ fontSize: '14px', fontWeight: 700, color: '#f1f5f9', lineHeight: 1.3 }}>{title}</div>
            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px', lineHeight: 1.4 }}>{sub}</div>
          </motion.div>
        </AnimatePresence>
      </foreignObject>
    </g>
  )
}
