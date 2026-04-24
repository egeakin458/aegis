import { Zap } from 'lucide-react'
import type { ProgressUpdateEntry } from '@/lib/types/ui'

export function ProgressUpdateLine({ entry }: { entry: ProgressUpdateEntry }) {
  return (
    <div className="flex items-center gap-2 py-1 pl-11">
      <Zap size={12} className="text-cyan-500" />
      <span className="text-xs text-slate-400">{entry.text}</span>
    </div>
  )
}
