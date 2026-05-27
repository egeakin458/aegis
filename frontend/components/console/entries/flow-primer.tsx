import { Sparkles } from 'lucide-react'

const STEPS = [
  { label: 'Requirements', desc: 'understand your idea' },
  { label: 'Design', desc: 'plan the structure' },
  { label: 'Build', desc: 'write the code' },
  { label: 'Review', desc: 'check the result' },
]

export function FlowPrimerCard() {
  return (
    <div className="border border-cyan-900/40 rounded-lg p-4 my-2 bg-gradient-to-br from-cyan-950/20 to-slate-950/0">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles size={14} className="text-cyan-400" />
        <span className="text-sm font-medium text-cyan-200">Four agents will build your app</span>
        <span className="text-xs text-slate-500 ml-auto">~4 min</span>
      </div>
      <div className="flex items-center gap-1.5 flex-wrap">
        {STEPS.map((s, i) => (
          <div key={s.label} className="flex items-center gap-1.5">
            <div className="px-2 py-1 rounded bg-slate-900/60 border border-slate-800">
              <div className="text-xs font-medium text-slate-200">{s.label}</div>
              <div className="text-[10px] text-slate-500">{s.desc}</div>
            </div>
            {i < STEPS.length - 1 && <span className="text-slate-600 text-xs">→</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
