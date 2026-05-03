'use client'

import { useFieldArray, useWatch } from 'react-hook-form'
import type { UseFormReturn } from 'react-hook-form'
import type { CustomerConfigV2 } from '@/lib/schemas/ddc'

const REL_KINDS = ['one_to_one', 'one_to_many', 'many_to_many'] as const

interface Props {
  form: UseFormReturn<CustomerConfigV2>
}

export function RelationshipsSection({ form }: Props) {
  const { register, control } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'relationships' })
  const entities = useWatch({ control, name: 'entities' }) ?? []

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">
        Define how entities relate to each other. Drives foreign key generation.
      </p>

      {fields.map((field, i) => (
        <div key={field.id} className="p-4 bg-slate-800/60 rounded-lg border border-slate-700 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-xs font-medium text-slate-300">Relationship {i + 1}</span>
            <button type="button" onClick={() => remove(i)} className="text-xs text-red-400 hover:text-red-300">
              Remove
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-slate-400 mb-1">From Entity</label>
              <select
                {...register(`relationships.${i}.from_entity_id`)}
                className="w-full px-2 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
              >
                <option value="">— select —</option>
                {entities.map((e) => e && (
                  <option key={e.id} value={e.id}>{e.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">To Entity</label>
              <select
                {...register(`relationships.${i}.to_entity_id`)}
                className="w-full px-2 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
              >
                <option value="">— select —</option>
                {entities.map((e) => e && (
                  <option key={e.id} value={e.id}>{e.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Kind</label>
              <select
                {...register(`relationships.${i}.kind`)}
                className="w-full px-2 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
              >
                {REL_KINDS.map(k => <option key={k} value={k}>{k.replace(/_/g, ' ')}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Role Name (snake_case)</label>
              <input
                {...register(`relationships.${i}.name`)}
                placeholder="order_items"
                className="w-full px-2 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
              />
            </div>
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={() => append({
          id: `rel_${Math.random().toString(36).slice(2, 10)}`,
          from_entity_id: '',
          to_entity_id: '',
          kind: 'one_to_many',
          name: '',
        })}
        className="w-full py-2 text-sm border border-dashed border-slate-600 text-slate-400 hover:text-slate-300 hover:border-slate-500 rounded-lg transition-colors"
      >
        + Add Relationship
      </button>
    </div>
  )
}
