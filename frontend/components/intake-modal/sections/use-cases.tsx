'use client'

import { useFieldArray, useWatch } from 'react-hook-form'
import type { UseFormReturn } from 'react-hook-form'
import type { CustomerConfigV2 } from '@/lib/schemas/ddc'

const USE_CASE_TYPES = ['command', 'query'] as const

interface Props {
  form: UseFormReturn<CustomerConfigV2>
}

export function UseCasesSection({ form }: Props) {
  const { register, control } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'use_cases' })
  const actors = useWatch({ control, name: 'actors' }) ?? []
  const entities = useWatch({ control, name: 'entities' }) ?? []
  const rules = useWatch({ control, name: 'business_rules' }) ?? []

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">
        Define what users can do. Each use case maps to one or more API endpoints.
      </p>

      {fields.map((field, i) => (
        <div key={field.id} className="p-4 bg-slate-800/60 rounded-lg border border-slate-700 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-xs font-medium text-slate-300">Use Case {i + 1}</span>
            <button type="button" onClick={() => remove(i)} className="text-xs text-red-400 hover:text-red-300">
              Remove
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Name</label>
              <input
                {...register(`use_cases.${i}.name`)}
                placeholder="Browse Products"
                className="w-full px-2 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Type</label>
              <select
                {...register(`use_cases.${i}.type`)}
                className="w-full px-2 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
              >
                {USE_CASE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Actor</label>
              <select
                {...register(`use_cases.${i}.actor_id`)}
                className="w-full px-2 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
              >
                <option value="">— select —</option>
                {actors.map((a) => a && (
                  <option key={a.id} value={a.id}>{a.role_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Primary Entity</label>
              <select
                {...register(`use_cases.${i}.primary_entity_id`)}
                className="w-full px-2 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
              >
                <option value="">— select —</option>
                {entities.map((e) => e && (
                  <option key={e.id} value={e.id}>{e.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Description (optional)</label>
            <input
              {...register(`use_cases.${i}.description`)}
              placeholder="Customer views the product catalog with filtering and sorting."
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
            />
          </div>

          {rules.length > 0 && (
            <div>
              <label className="block text-xs text-slate-400 mb-1">Business Rules (optional)</label>
              <div className="space-y-1">
                {rules.map((r) => r && (
                  <label key={r.id} className="flex items-center gap-2 text-xs text-slate-300">
                    <input
                      type="checkbox"
                      value={r.id}
                      {...register(`use_cases.${i}.business_rule_ids`)}
                      className="rounded border-slate-600 bg-slate-900 text-cyan-500"
                    />
                    {r.description.slice(0, 60)}{r.description.length > 60 ? '…' : ''}
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}

      <button
        type="button"
        onClick={() => append({
          id: `uc_${Math.random().toString(36).slice(2, 10)}`,
          name: '',
          type: 'query',
          actor_id: actors[0]?.id ?? '',
          primary_entity_id: entities[0]?.id ?? '',
          business_rule_ids: [],
          description: null,
        })}
        className="w-full py-2 text-sm border border-dashed border-slate-600 text-slate-400 hover:text-slate-300 hover:border-slate-500 rounded-lg transition-colors"
      >
        + Add Use Case
      </button>
    </div>
  )
}
