'use client'
import { motion } from 'framer-motion'
import type { AgentId } from '@/lib/types/ui'

const LABELS: Record<AgentId, string> = {
  ra: 'Requirements', sa: 'Architecture', dev: 'Developer', qa: 'QA Review',
}
const SHORT: Record<AgentId, string> = { ra: 'RA', sa: 'SA', dev: 'DEV', qa: 'QA' }

type NodeState = 'idle' | 'active' | 'waiting' | 'complete' | 'error'

interface Props {
  agent: AgentId
  state: NodeState
  x: number
  y: number
}

const STATE_COLORS: Record<NodeState, { ring: string; bg: string; text: string }> = {
  idle: { ring: '#334155', bg: '#1e293b', text: '#64748b' },
  active: { ring: '#22d3ee', bg: '#0e4f5c', text: '#22d3ee' },
  waiting: { ring: '#f59e0b', bg: '#3d2800', text: '#f59e0b' },
  complete: { ring: '#10b981', bg: '#064e35', text: '#10b981' },
  error: { ring: '#ef4444', bg: '#2d0a0a', text: '#ef4444' },
}

export function AgentNode({ agent, state, x, y }: Props) {
  const colors = STATE_COLORS[state]
  const isActive = state === 'active'
  const isWaiting = state === 'waiting'

  return (
    <g transform={`translate(${x}, ${y})`}>
      <defs>
        <filter id={`node-glow-${agent}`}>
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {/* Pulse ring for active/waiting */}
      {(isActive || isWaiting) && (
        <motion.circle
          r={30}
          fill="none"
          stroke={colors.ring}
          strokeWidth={1}
          initial={{ r: 30, opacity: 0.8 }}
          animate={{ r: 46, opacity: 0 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
        />
      )}
      {/* Second delayed pulse ring */}
      {(isActive || isWaiting) && (
        <motion.circle
          r={30}
          fill="none"
          stroke={colors.ring}
          strokeWidth={1}
          initial={{ r: 30, opacity: 0.8 }}
          animate={{ r: 46, opacity: 0 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut', delay: 0.6 }}
        />
      )}
      {/* Amber notification dot for waiting */}
      {isWaiting && (
        <motion.circle
          cx={16}
          cy={-16}
          r={5}
          fill="#f59e0b"
          animate={{ scale: [1, 1.3, 1] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}
      {/* Main circle */}
      <motion.circle
        r={30}
        fill={colors.bg}
        stroke={colors.ring}
        strokeWidth={isActive ? 2.5 : 1.5}
        animate={{ strokeWidth: isActive ? [2, 3, 2] : 1.5 }}
        transition={{ duration: 2, repeat: isActive ? Infinity : 0 }}
        filter={isActive ? `url(#node-glow-${agent})` : undefined}
      />
      {/* Monogram */}
      <text
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={13}
        fontWeight={700}
        fontFamily="monospace"
        fill={colors.text}
      >
        {SHORT[agent]}
      </text>
      {/* Label below */}
      <text
        y={46}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={11}
        fill="#94a3b8"
      >
        {LABELS[agent]}
      </text>
    </g>
  )
}
