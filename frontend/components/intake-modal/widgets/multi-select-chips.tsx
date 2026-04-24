'use client'
import { cn } from '@/lib/utils'

interface Props {
  options: string[]
  value: string[]
  onChange: (v: string[]) => void
}

export function MultiSelectChips({ options, value, onChange }: Props) {
  function toggle(opt: string) {
    onChange(value.includes(opt) ? value.filter(v => v !== opt) : [...value, opt])
  }

  return (
    <div className="flex flex-wrap gap-2">
      {options.map(opt => (
        <button
          key={opt}
          type="button"
          onClick={() => toggle(opt)}
          className={cn(
            'px-3 py-1.5 rounded-full text-xs font-medium border transition-colors',
            value.includes(opt)
              ? 'bg-cyan-900/50 border-cyan-700 text-cyan-300'
              : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-300'
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
