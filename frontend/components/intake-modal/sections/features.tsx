'use client'
import { Controller } from 'react-hook-form'
import type { IntakeFormReturn } from '@/lib/schemas/intake-form'
import { FeatureList } from '../widgets/feature-list'
import { TagInput } from '../widgets/tag-input'

interface Props { form: IntakeFormReturn }

export function FeaturesSection({ form }: Props) {
  const { control, formState: { errors } } = form

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Must-Have Features</label>
        <Controller
          control={control}
          name="mustHaveFeatures"
          render={({ field }) => (
            <FeatureList value={field.value} onChange={field.onChange} />
          )}
        />
        {errors.mustHaveFeatures && <p className="text-xs text-red-400 mt-1">Add at least one feature</p>}
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Nice-to-Have Features <span className="text-slate-500">(optional)</span></label>
        <Controller
          control={control}
          name="niceToHaveFeatures"
          render={({ field }) => (
            <TagInput
              value={field.value}
              onChange={field.onChange}
              placeholder="e.g. Dark mode — press Enter"
            />
          )}
        />
      </div>
    </div>
  )
}
