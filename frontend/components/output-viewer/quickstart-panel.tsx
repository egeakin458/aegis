'use client'
import { useState } from 'react'
import { Copy, Check, Sparkles } from 'lucide-react'

interface Props {
  runId: string
}

export function QuickstartPanel({ runId }: Props) {
  const commands = [
    `cd backend/outputs/${runId}`,
    'npm install',
    'npm run dev -- -p 3100',
  ]
  const allCommands = commands.join('\n')
  const [copied, setCopied] = useState<number | 'all' | null>(null)

  function copy(text: string, key: number | 'all') {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(null), 1500)
    })
  }

  return (
    <div className="border-b border-slate-800 px-4 py-3 bg-slate-900/40">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles size={14} className="text-cyan-400" />
        <span className="text-sm font-medium text-slate-200">Your app is ready</span>
        <button
          type="button"
          onClick={() => copy(allCommands, 'all')}
          className="ml-auto text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
        >
          {copied === 'all' ? <Check size={12} /> : <Copy size={12} />}
          {copied === 'all' ? 'Copied' : 'Copy all'}
        </button>
      </div>
      <p className="text-xs text-slate-400 mb-2">
        Run these three commands in a terminal at the repo root to launch the generated app on{' '}
        <span className="font-mono text-slate-300">http://localhost:3100</span>.
      </p>
      <div className="space-y-1">
        {commands.map((cmd, i) => (
          <div
            key={i}
            className="flex items-center gap-2 rounded bg-slate-950/60 border border-slate-800/60 px-2 py-1.5"
          >
            <span className="text-xs text-slate-600 font-mono select-none">$</span>
            <code className="flex-1 text-xs font-mono text-slate-200 truncate">{cmd}</code>
            <button
              type="button"
              onClick={() => copy(cmd, i)}
              className="text-slate-500 hover:text-cyan-300 transition-colors"
              aria-label="Copy command"
            >
              {copied === i ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
            </button>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-500 mt-2">
        First-time install compiles a native binding (~30–60 s). Requires Node 18+, plus{' '}
        <span className="font-mono">build-essential</span> and{' '}
        <span className="font-mono">python3</span> on Linux.
      </p>
    </div>
  )
}
