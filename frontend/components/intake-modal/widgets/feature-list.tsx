'use client'
import { useState } from 'react'
import { Plus, Trash2, GripVertical } from 'lucide-react'
import type { FeatureItem } from '@/lib/schemas/intake-form'

export type { FeatureItem }

interface Props {
  value: FeatureItem[]
  onChange: (v: FeatureItem[]) => void
}

export function FeatureList({ value, onChange }: Props) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')

  function add() {
    if (!name.trim()) return
    onChange([...value, { id: crypto.randomUUID(), name: name.trim(), description: desc.trim(), priority: value.length + 1 }])
    setName('')
    setDesc('')
  }

  function remove(id: string) {
    const updated = value.filter(f => f.id !== id).map((f, i) => ({ ...f, priority: i + 1 }))
    onChange(updated)
  }

  return (
    <div className="space-y-2">
      {value.map((f, i) => (
        <div key={f.id} className="flex items-start gap-2 p-3 rounded-lg bg-slate-800 border border-slate-700">
          <GripVertical size={14} className="text-slate-600 mt-0.5 shrink-0" />
          <span className="text-xs font-bold text-slate-500 mt-0.5 w-4 shrink-0">{i + 1}</span>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-slate-200">{f.name}</p>
            {f.description && <p className="text-xs text-slate-500 mt-0.5">{f.description}</p>}
          </div>
          <button type="button" onClick={() => remove(f.id)} className="text-slate-600 hover:text-red-400 transition-colors shrink-0">
            <Trash2 size={13} />
          </button>
        </div>
      ))}
      <div className="flex gap-2">
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder="Feature name"
          className="flex-1 px-3 py-2 text-xs rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
        />
        <input
          value={desc}
          onChange={e => setDesc(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder="Description (optional)"
          className="flex-1 px-3 py-2 text-xs rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
        />
        <button
          type="button"
          onClick={add}
          className="px-3 py-2 rounded-lg bg-cyan-900/50 border border-cyan-700 text-cyan-300 hover:bg-cyan-900 transition-colors"
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  )
}
