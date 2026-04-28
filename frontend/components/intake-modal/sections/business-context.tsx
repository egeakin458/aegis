'use client'
import { Controller } from 'react-hook-form'
import type { IntakeFormReturn } from '@/lib/schemas/intake-form'
import { SegmentedToggle } from '../widgets/segmented-toggle'
import { MultiSelectChips } from '../widgets/multi-select-chips'

interface Props { form: IntakeFormReturn }

export function BusinessContextSection({ form }: Props) {
  const { register, control, formState: { errors } } = form

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Company Name</label>
        <input
          {...register('companyName')}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
          placeholder="Acme Inc."
        />
        {errors.companyName && <p className="text-xs text-red-400 mt-1">{errors.companyName.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Industry</label>
        <Controller
          control={control}
          name="industry"
          render={({ field }) => (
            <MultiSelectChips
              options={['Retail', 'Food & Beverage', 'Professional Services', 'Healthcare', 'Education', 'Manufacturing', 'Other']}
              value={[field.value]}
              onChange={v => field.onChange(v[v.length - 1] ?? field.value)}
            />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Business Size</label>
        <Controller
          control={control}
          name="businessSize"
          render={({ field }) => (
            <SegmentedToggle
              options={['1–5', '6–20', '21–50', '50+']}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Who will use this app?</label>
        <Controller
          control={control}
          name="targetUsers"
          render={({ field }) => (
            <MultiSelectChips
              options={['Owner', 'Employees', 'Customers', 'All Users']}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
        {errors.targetUsers && <p className="text-xs text-red-400 mt-1">{errors.targetUsers.message}</p>}
      </div>
    </div>
  )
}
