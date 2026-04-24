'use client'
import { cn } from '@/lib/utils'

interface Props {
  options: string[]
  value: string
  onChange: (v: string) => void
}

export function SegmentedToggle({ options, value, onChange }: Props) {
  return (
    <div className="flex rounded-lg border border-slate-700 overflow-hidden">
      {options.map(opt => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={cn(
            'flex-1 px-3 py-2 text-xs font-medium transition-colors',
            value === opt
              ? 'bg-[#22d3ee] text-[#0f172a]'
              : 'bg-slate-800 text-slate-400 hover:text-slate-200'
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
