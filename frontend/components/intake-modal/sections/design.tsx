'use client'
import { Controller } from 'react-hook-form'
import type { IntakeFormReturn } from '@/lib/schemas/intake-form'
import { SegmentedToggle } from '../widgets/segmented-toggle'
import { ColorPicker } from '../widgets/color-picker'
import { TagInput } from '../widgets/tag-input'

interface Props { form: IntakeFormReturn }

export function DesignSection({ form }: Props) {
  const { control } = form

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Visual Style</label>
        <Controller
          control={control}
          name="visualStyle"
          render={({ field }) => (
            <SegmentedToggle
              options={['Clean & Minimal', 'Professional & Corporate', 'Modern & Colorful', 'No Preference']}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Color Preferences <span className="text-slate-500">(optional)</span></label>
        <Controller
          control={control}
          name="colorPreferences"
          render={({ field }) => (
            <ColorPicker value={field.value} onChange={field.onChange} />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Mobile Support</label>
        <Controller
          control={control}
          name="mobileSupport"
          render={({ field }) => (
            <SegmentedToggle
              options={['Yes', 'No', 'Nice to Have']}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Example Sites <span className="text-slate-500">(optional)</span></label>
        <Controller
          control={control}
          name="exampleSites"
          render={({ field }) => (
            <TagInput
              value={field.value}
              onChange={field.onChange}
              placeholder="e.g. notion.so, linear.app — press Enter"
            />
          )}
        />
      </div>
    </div>
  )
}
