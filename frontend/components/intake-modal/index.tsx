'use client'
import { useState } from 'react'
import { X } from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'

const SECTIONS = [
  'Business Context',
  'Problem Statement',
  'Features',
  'Data & Content',
  'Design',
  'Technical',
  'Timeline',
]

interface Props {
  open: boolean
  onClose: () => void
}

export function IntakeModal({ open, onClose }: Props) {
  const [section, setSection] = useState(0)

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent className="max-w-2xl bg-[#0f1729] border-slate-700 text-slate-200 p-0 overflow-hidden">
        {/* Progress bar */}
        <div className="h-1 bg-slate-800">
          <div
            className="h-full bg-[#22d3ee] transition-all duration-300"
            style={{ width: `${((section + 1) / SECTIONS.length) * 100}%` }}
          />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div>
            <h2 className="text-base font-semibold">New Project</h2>
            <p className="text-xs text-slate-400">{section + 1} / {SECTIONS.length} — {SECTIONS[section]}</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Section tabs */}
        <div className="flex gap-1 px-6 pt-4 flex-wrap">
          {SECTIONS.map((s, i) => (
            <button
              key={s}
              onClick={() => setSection(i)}
              className={`text-xs px-3 py-1 rounded-full transition-colors ${
                i === section
                  ? 'bg-[#22d3ee] text-[#0f172a] font-medium'
                  : i < section
                  ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-300'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Content placeholder */}
        <div className="px-6 py-6 min-h-[280px] flex items-center justify-center">
          <p className="text-slate-500 text-sm">{SECTIONS[section]} — form fields coming in Phase 2</p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800">
          <button
            onClick={() => setSection(s => Math.max(0, s - 1))}
            disabled={section === 0}
            className="px-4 py-2 text-sm rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 disabled:opacity-40 transition-colors"
          >
            Back
          </button>
          {section < SECTIONS.length - 1 ? (
            <button
              onClick={() => setSection(s => s + 1)}
              className="px-4 py-2 text-sm rounded-lg bg-[#22d3ee] text-[#0f172a] font-medium hover:bg-cyan-300 transition-colors"
            >
              Next
            </button>
          ) : (
            <button
              className="px-4 py-2 text-sm rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-500 transition-colors"
            >
              Start Pipeline
            </button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
