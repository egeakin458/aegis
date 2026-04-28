'use client'
import { useState, KeyboardEvent } from 'react'
import { X } from 'lucide-react'

interface Props {
  value: string[]
  onChange: (v: string[]) => void
  placeholder?: string
}

export function TagInput({ value, onChange, placeholder = 'Type and press Enter...' }: Props) {
  const [input, setInput] = useState('')

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    if ((e.key === 'Enter' || e.key === ',') && input.trim()) {
      e.preventDefault()
      if (!value.includes(input.trim())) {
        onChange([...value, input.trim()])
      }
      setInput('')
    }
    if (e.key === 'Backspace' && !input && value.length) {
      onChange(value.slice(0, -1))
    }
  }

  return (
    <div className="flex flex-wrap gap-1.5 min-h-[40px] px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 focus-within:border-cyan-700">
      {value.map(tag => (
        <span key={tag} className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-700 text-xs text-slate-200">
          {tag}
          <button type="button" onClick={() => onChange(value.filter(v => v !== tag))} className="text-slate-400 hover:text-white">
            <X size={10} />
          </button>
        </span>
      ))}
      <input
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKey}
        placeholder={value.length === 0 ? placeholder : ''}
        className="flex-1 min-w-[120px] bg-transparent text-xs text-slate-200 placeholder:text-slate-600 outline-none"
      />
    </div>
  )
}
