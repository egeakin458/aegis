'use client'
import { Controller } from 'react-hook-form'
import type { IntakeFormReturn } from '@/lib/schemas/intake-form'
import { SegmentedToggle } from '../widgets/segmented-toggle'
import { MultiSelectChips } from '../widgets/multi-select-chips'
import { TagInput } from '../widgets/tag-input'

interface Props { form: IntakeFormReturn }

const DATA_TYPE_OPTIONS = ['Products / Inventory', 'Customers / Users', 'Orders / Transactions', 'Documents / Files', 'Analytics / Reports', 'Appointments / Bookings', 'Content / Articles']

export function DataContentSection({ form }: Props) {
  const { control } = form

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">What types of data will your app manage?</label>
        <Controller
          control={control}
          name="dataTypes"
          render={({ field }) => (
            <MultiSelectChips
              options={DATA_TYPE_OPTIONS}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Approximate number of records</label>
        <Controller
          control={control}
          name="dataVolume"
          render={({ field }) => (
            <SegmentedToggle
              options={['Under 100', '100–1,000', '1,000–10,000', '10,000+']}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">External Integrations <span className="text-slate-500">(optional)</span></label>
        <Controller
          control={control}
          name="externalIntegrations"
          render={({ field }) => (
            <TagInput
              value={field.value}
              onChange={field.onChange}
              placeholder="e.g. Stripe, Google Sheets — press Enter"
            />
          )}
        />
      </div>
    </div>
  )
}
