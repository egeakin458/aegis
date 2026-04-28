'use client'
import { Controller } from 'react-hook-form'
import type { IntakeFormReturn } from '@/lib/schemas/intake-form'
import { SegmentedToggle } from '../widgets/segmented-toggle'
import { TagInput } from '../widgets/tag-input'

interface Props { form: IntakeFormReturn }

export function TechnicalSection({ form }: Props) {
  const { control } = form

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Who can access this app?</label>
        <Controller
          control={control}
          name="accessScope"
          render={({ field }) => (
            <SegmentedToggle
              options={['Just Me', 'Team / Network', 'Anyone on the Internet']}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Performance Requirements <span className="text-slate-500">(optional)</span></label>
        <Controller
          control={control}
          name="performanceRequirements"
          render={({ field }) => (
            <TagInput
              value={field.value}
              onChange={field.onChange}
              placeholder="e.g. Must load in under 2 seconds — press Enter"
            />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Security Requirements <span className="text-slate-500">(optional)</span></label>
        <Controller
          control={control}
          name="securityRequirements"
          render={({ field }) => (
            <TagInput
              value={field.value}
              onChange={field.onChange}
              placeholder="e.g. Password-protected admin panel — press Enter"
            />
          )}
        />
      </div>
    </div>
  )
}
