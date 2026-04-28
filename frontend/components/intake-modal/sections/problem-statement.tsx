'use client'
import { Controller } from 'react-hook-form'
import type { IntakeFormReturn } from '@/lib/schemas/intake-form'
import { TagInput } from '../widgets/tag-input'

interface Props { form: IntakeFormReturn }

export function ProblemStatementSection({ form }: Props) {
  const { register, control, formState: { errors } } = form

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Current Situation</label>
        <textarea
          {...register('currentSituation')}
          rows={3}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700 resize-none"
          placeholder="Describe how things work today and what's painful..."
        />
        {errors.currentSituation && <p className="text-xs text-red-400 mt-1">{errors.currentSituation.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Desired Outcome</label>
        <textarea
          {...register('desiredOutcome')}
          rows={3}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700 resize-none"
          placeholder="What does success look like? What should the app do?"
        />
        {errors.desiredOutcome && <p className="text-xs text-red-400 mt-1">{errors.desiredOutcome.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Pain Points <span className="text-slate-500">(optional)</span></label>
        <Controller
          control={control}
          name="painPoints"
          render={({ field }) => (
            <TagInput
              value={field.value}
              onChange={field.onChange}
              placeholder="e.g. Manual data entry is slow — press Enter"
            />
          )}
        />
      </div>
    </div>
  )
}
