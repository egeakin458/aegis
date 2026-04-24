'use client'
import { cn } from '@/lib/utils'

const PRESETS = ['#22d3ee', '#9333ea', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899', '#f97316']

interface Props {
  value: string[]
  onChange: (v: string[]) => void
}

export function ColorPicker({ value, onChange }: Props) {
  function toggle(color: string) {
    onChange(value.includes(color) ? value.filter(c => c !== color) : [...value, color])
  }

  return (
    <div className="flex gap-2 flex-wrap">
      {PRESETS.map(color => (
        <button
          key={color}
          type="button"
          onClick={() => toggle(color)}
          className={cn(
            'w-8 h-8 rounded-full border-2 transition-all',
            value.includes(color) ? 'border-white scale-110' : 'border-transparent hover:border-slate-500'
          )}
          style={{ backgroundColor: color }}
          title={color}
        />
      ))}
    </div>
  )
}
