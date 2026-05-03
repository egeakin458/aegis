'use client'

import { useFieldArray, useWatch } from 'react-hook-form'
import type { UseFormReturn } from 'react-hook-form'
import type { CustomerConfigV2 } from '@/lib/schemas/ddc'

const DATA_FIELD_TYPES = [
  'string', 'text', 'integer', 'decimal', 'boolean', 'datetime', 'date', 'uuid', 'json',
] as const

interface Props {
  form: UseFormReturn<CustomerConfigV2>
}

function AttributeList({ form, entityIndex }: { form: UseFormReturn<CustomerConfigV2>; entityIndex: number }) {
  const { register, control } = form
  const { fields, append, remove } = useFieldArray({
    control,
    name: `entities.${entityIndex}.attributes`,
  })

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">Attributes</p>
      {fields.map((field, j) => (
        <div key={field.id} className="flex gap-2 items-center">
          <input
            {...register(`entities.${entityIndex}.attributes.${j}.name`)}
            placeholder="attribute_name"
            className="flex-1 px-2 py-1 text-xs rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
          />
          <select
            {...register(`entities.${entityIndex}.attributes.${j}.type`)}
            className="px-2 py-1 text-xs rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
          >
            {DATA_FIELD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button
            type="button"
            onClick={() => remove(j)}
            className="text-xs text-red-400 hover:text-red-300"
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => append({ name: '', type: 'string', required: true, unique: false })}
        className="text-xs text-cyan-500 hover:text-cyan-400"
      >
        + Add attribute
      </button>
    </div>
  )
}

export function EntitiesSection({ form }: Props) {
  const { register, control } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'entities' })
  const actors = useWatch({ control, name: 'actors' }) ?? []

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">
        Define the data entities (database tables) your application needs.
      </p>

      {fields.map((field, i) => (
        <div key={field.id} className="p-4 bg-slate-800/60 rounded-lg border border-slate-700 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-xs font-medium text-slate-300">Entity {i + 1}</span>
            <button type="button" onClick={() => remove(i)} className="text-xs text-red-400 hover:text-red-300">
              Remove
            </button>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Entity Name (PascalCase)</label>
            <input
              {...register(`entities.${i}.name`)}
              placeholder="Product"
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Owned By Actor (optional)</label>
            <select
              {...register(`entities.${i}.owned_by_actor_id`)}
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
            >
              <option value="">— none —</option>
              {actors.map((a) => a && (
                <option key={a.id} value={a.id}>{a.role_name}</option>
              ))}
            </select>
          </div>

          <AttributeList form={form} entityIndex={i} />
        </div>
      ))}

      <button
        type="button"
        onClick={() => append({
          id: `ent_${Math.random().toString(36).slice(2, 10)}`,
          name: '',
          attributes: [{ name: 'name', type: 'string', required: true, unique: false }],
          states: ['Active'],
          owned_by_actor_id: null,
        })}
        className="w-full py-2 text-sm border border-dashed border-slate-600 text-slate-400 hover:text-slate-300 hover:border-slate-500 rounded-lg transition-colors"
      >
        + Add Entity
      </button>
    </div>
  )
}
