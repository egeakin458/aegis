'use client'
import type { IntakeFormReturn } from '@/lib/schemas/intake-form'

interface Props { form: IntakeFormReturn }

export function TimelineSection({ form }: Props) {
  const { register } = form

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Project Name</label>
        <input
          {...register('projectName')}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
          placeholder="My Inventory App"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Deadline <span className="text-slate-500">(optional)</span></label>
        <input
          {...register('deadline')}
          type="date"
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-700 [color-scheme:dark]"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Budget Range <span className="text-slate-500">(optional)</span></label>
        <input
          {...register('budgetRange')}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
          placeholder="e.g. Under $5,000"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Additional Context <span className="text-slate-500">(optional)</span></label>
        <textarea
          {...register('additionalContext')}
          rows={3}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700 resize-none"
          placeholder="Anything else the AI should know..."
        />
      </div>
    </div>
  )
}
