import { FileCode } from 'lucide-react'
import type { FileGeneratedEntry } from '@/lib/types/ui'

export function FileGeneratedCard({ entry }: { entry: FileGeneratedEntry }) {
  return (
    <div className="flex items-center gap-2 py-1 pl-11">
      <FileCode size={13} className="text-blue-400" />
      <span className="text-xs font-mono text-blue-300">{entry.path}</span>
      <span className="text-xs text-slate-600">{entry.language}</span>
    </div>
  )
}
