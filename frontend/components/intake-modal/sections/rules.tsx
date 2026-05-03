'use client'

import { useFieldArray } from 'react-hook-form'
import type { UseFormReturn } from 'react-hook-form'
import type { CustomerConfigV2 } from '@/lib/schemas/ddc'

interface Props {
  form: UseFormReturn<CustomerConfigV2>
}

export function BusinessRulesSection({ form }: Props) {
  const { register, control } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'business_rules' })

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">
        Define constraints and invariants the generated code must enforce.
      </p>

      {fields.map((field, i) => (
        <div key={field.id} className="p-4 bg-slate-800/60 rounded-lg border border-slate-700 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-xs font-medium text-slate-300">Rule {i + 1}</span>
            <button type="button" onClick={() => remove(i)} className="text-xs text-red-400 hover:text-red-300">
              Remove
            </button>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Description</label>
            <textarea
              {...register(`business_rules.${i}.description`)}
              rows={2}
              placeholder="Product stock must be sufficient before an order can be confirmed."
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700 resize-none"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Trigger Condition</label>
            <input
              {...register(`business_rules.${i}.trigger_condition`)}
              placeholder="When Order transitions from Pending to Confirmed"
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Enforcement Action</label>
            <input
              {...register(`business_rules.${i}.enforcement_action`)}
              placeholder="Reject with 422 if OrderItem.quantity exceeds Product.stock"
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
            />
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={() => append({
          id: `rule_${Math.random().toString(36).slice(2, 10)}`,
          description: '',
          trigger_condition: '',
          enforcement_action: '',
        })}
        className="w-full py-2 text-sm border border-dashed border-slate-600 text-slate-400 hover:text-slate-300 hover:border-slate-500 rounded-lg transition-colors"
      >
        + Add Business Rule
      </button>
    </div>
  )
}
