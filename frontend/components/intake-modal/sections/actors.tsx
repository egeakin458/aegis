'use client'

import { useFieldArray } from 'react-hook-form'
import type { UseFormReturn } from 'react-hook-form'
import type { CustomerConfigV2 } from '@/lib/schemas/ddc'

const AUTH_METHODS = ['anonymous', 'email_password', 'invite_only', 'sso'] as const

interface Props {
  form: UseFormReturn<CustomerConfigV2>
}

export function ActorsSection({ form }: Props) {
  const { register, control, formState: { errors } } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'actors' })

  const actorErrors = (errors.actors as Record<number, Record<string, { message?: string }>> | undefined)

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">
        Define who will use the application. Each actor represents a distinct role.
      </p>

      {fields.map((field, i) => (
        <div key={field.id} className="p-4 bg-slate-800/60 rounded-lg border border-slate-700 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-xs font-medium text-slate-300">Actor {i + 1}</span>
            <button
              type="button"
              onClick={() => remove(i)}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Remove
            </button>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Role Name (PascalCase)</label>
            <input
              {...register(`actors.${i}.role_name`)}
              placeholder="Customer"
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
            />
            {actorErrors?.[i]?.role_name && (
              <p className="text-xs text-red-400 mt-0.5">{actorErrors[i].role_name.message}</p>
            )}
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Auth Method</label>
            <select
              {...register(`actors.${i}.auth_method`)}
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 focus:outline-none focus:border-cyan-700"
            >
              {AUTH_METHODS.map(m => (
                <option key={m} value={m}>{m.replace('_', ' ')}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Permissions Description</label>
            <textarea
              {...register(`actors.${i}.permissions_description`)}
              rows={2}
              placeholder="Can browse products, place orders, and view order history."
              className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-600 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700 resize-none"
            />
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={() => append({
          id: `act_${Math.random().toString(36).slice(2, 10)}`,
          role_name: '',
          auth_method: 'anonymous',
          permissions_description: '',
        })}
        className="w-full py-2 text-sm border border-dashed border-slate-600 text-slate-400 hover:text-slate-300 hover:border-slate-500 rounded-lg transition-colors"
      >
        + Add Actor
      </button>
    </div>
  )
}
