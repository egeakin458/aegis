import {
  Play, CheckCircle, MessageSquare, Zap, FileCode,
  HelpCircle, ClipboardCheck, AlertTriangle, XCircle, Trophy,
  type LucideIcon,
} from 'lucide-react'
import type { ConsoleEntryType } from '@/lib/types/ui'

const ICONS: Record<ConsoleEntryType, LucideIcon> = {
  'agent-start': Play,
  'agent-complete': CheckCircle,
  'message': MessageSquare,
  'progress-update': Zap,
  'file-generated': FileCode,
  'clarification': HelpCircle,
  'config-finalized': ClipboardCheck,
  'revision-requested': AlertTriangle,
  'error-entry': XCircle,
  'summary': Trophy,
}

const COLORS: Record<ConsoleEntryType, string> = {
  'agent-start': 'text-cyan-400',
  'agent-complete': 'text-emerald-400',
  'message': 'text-slate-400',
  'progress-update': 'text-cyan-400',
  'file-generated': 'text-blue-400',
  'clarification': 'text-amber-400',
  'config-finalized': 'text-emerald-400',
  'revision-requested': 'text-amber-400',
  'error-entry': 'text-red-400',
  'summary': 'text-emerald-400',
}

export function TypeIcon({ type }: { type: ConsoleEntryType }) {
  const Icon = ICONS[type]
  return <Icon size={16} className={COLORS[type]} />
}
