/* eslint-disable @typescript-eslint/no-explicit-any */
'use client'
import { motion } from 'framer-motion'

interface Props {
  cx: number
  cy: number
  r: number
  activeSegment: number | null  // 0=RA→SA, 1=SA→DEV, 2=DEV→QA
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polarToCartesian(cx, cy, r, startDeg)
  const e = polarToCartesian(cx, cy, r, endDeg)
  const large = endDeg - startDeg > 180 ? 1 : 0
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`
}

// 4 agents at 0°(top), 90°(right), 180°(bottom), 270°(left)
// Arcs between them: 0→90, 90→180, 180→270, 270→360
const ARCS = [
  { start: 0, end: 90 },   // RA → SA
  { start: 90, end: 180 },  // SA → DEV
  { start: 180, end: 270 }, // DEV → QA
  { start: 270, end: 360 }, // QA → RA (feedback)
]

export function OrbitArcs({ cx, cy, r, activeSegment }: Props) {
  return (
    <motion.g
      style={{ transformOrigin: `${cx}px ${cy}px` }}
      animate={{ rotate: 0 }}
      transition={{ duration: 0 }}
    >
      {ARCS.map((arc, i) => {
        const d = arcPath(cx, cy, r, arc.start, arc.end)
        const isActive = activeSegment === i
        const isCompleted = activeSegment !== null && i < activeSegment
        return (
          <g key={i}>
            {/* Completed arc trail */}
            {isCompleted && (
              <path d={d} fill="none" stroke="#10b981" strokeWidth={1.5} opacity={0.35} />
            )}
            {/* Base arc */}
            <path d={d} fill="none" stroke="#1e3a4a" strokeWidth={2} />
            {/* Active arc */}
            {isActive && (
              <>
                <path d={d} fill="none" stroke="#22d3ee" strokeWidth={2.5} />
                {/* Comet */}
                <motion.circle
                  r={5}
                  fill="#22d3ee"
                  filter="url(#comet-glow)"
                  initial={{ offsetDistance: '0%' } as any}
                  animate={{ offsetDistance: '100%' } as any}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                  style={{ offsetPath: `path("${d}")` } as any}
                />
                {/* Comet tail */}
                <motion.circle
                  r={3}
                  fill="#22d3ee"
                  opacity={0.4}
                  initial={{ offsetDistance: '0%' } as any}
                  animate={{ offsetDistance: '100%' } as any}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear', delay: 0.15 }}
                  style={{ offsetPath: `path("${d}")` } as any}
                />
              </>
            )}
          </g>
        )
      })}
      <defs>
        <filter id="comet-glow">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
    </motion.g>
  )
}
