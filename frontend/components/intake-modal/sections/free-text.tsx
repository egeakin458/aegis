'use client'

import { Controller } from 'react-hook-form'
import type { UseFormReturn } from 'react-hook-form'
import type { FreeTextFormValues } from '@/lib/schemas/intake-form'

const INDUSTRY_OPTIONS: { label: string; value: FreeTextFormValues['industry'] }[] = [
  { label: 'Retail', value: 'retail' },
  { label: 'Healthcare', value: 'healthcare' },
  { label: 'Education', value: 'education' },
  { label: 'Finance', value: 'finance' },
  { label: 'Services', value: 'services' },
  { label: 'Other', value: 'other' },
]

const STYLE_OPTIONS: { label: string; value: FreeTextFormValues['visualStyle'] }[] = [
  { label: 'Clean & Minimal', value: 'clean_minimal' },
  { label: 'Bold & Modern', value: 'bold_modern' },
  { label: 'Warm & Friendly', value: 'warm_friendly' },
  { label: 'Professional', value: 'professional_corporate' },
  { label: 'Playful', value: 'playful' },
]

const EXAMPLES: { label: string; values: Partial<FreeTextFormValues> }[] = [
  {
    label: 'Todo list',
    values: {
      projectName: 'taskmaster',
      domainDescription:
        'A personal task manager where a single user can create tasks with a title and optional description, organize them into categories, mark tasks complete, and delete tasks they have finished. Tasks can be filtered by category.',
      industry: 'other',
      visualStyle: 'clean_minimal',
      mobileFirst: true,
    },
  },
  {
    label: 'Inventory tracker',
    values: {
      projectName: 'stockwatch',
      domainDescription:
        'A small-business inventory tracker. A staff member can add products with name, SKU, price, and current stock; record stock-in and stock-out events; and see a low-stock alert list. Products can be grouped by category and searched by name.',
      industry: 'retail',
      visualStyle: 'professional_corporate',
      mobileFirst: false,
    },
  },
  {
    label: 'Event RSVP',
    values: {
      projectName: 'rsvp-board',
      domainDescription:
        'An event RSVP board. An organizer creates events with a title, date, and location. Guests can browse upcoming events, RSVP yes/no/maybe, and leave a short note. The organizer sees a per-event guest list and counts of each RSVP status.',
      industry: 'services',
      visualStyle: 'warm_friendly',
      mobileFirst: true,
    },
  },
]

interface Props {
  form: UseFormReturn<FreeTextFormValues>
}

export function FreeTextSection({ form }: Props) {
  const { register, control, setValue, formState: { errors } } = form

  function applyExample(values: Partial<FreeTextFormValues>) {
    for (const [k, v] of Object.entries(values)) {
      setValue(k as keyof FreeTextFormValues, v as never, { shouldValidate: true, shouldDirty: true })
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Start from an example</label>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map(ex => (
            <button
              key={ex.label}
              type="button"
              onClick={() => applyExample(ex.values)}
              className="px-3 py-1.5 text-xs rounded-full bg-slate-800 border border-slate-700 text-slate-300 hover:border-cyan-700 hover:text-cyan-200 transition-colors"
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">
          Project Name
        </label>
        <input
          {...register('projectName')}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700"
          placeholder="my-app"
        />
        {errors.projectName && (
          <p className="text-xs text-red-400 mt-1">{errors.projectName.message}</p>
        )}
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">
          Describe your application
          <span className="text-slate-500 ml-1">(50–1500 characters)</span>
        </label>
        <textarea
          {...register('domainDescription')}
          rows={5}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-700 resize-none"
          placeholder="Describe what your app should do, who will use it, and what business problems it solves..."
        />
        {errors.domainDescription && (
          <p className="text-xs text-red-400 mt-1">{errors.domainDescription.message}</p>
        )}
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Industry</label>
        <Controller
          control={control}
          name="industry"
          render={({ field }) => (
            <select
              value={field.value}
              onChange={e => field.onChange(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-700"
            >
              {INDUSTRY_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Visual Style</label>
        <Controller
          control={control}
          name="visualStyle"
          render={({ field }) => (
            <select
              value={field.value}
              onChange={e => field.onChange(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-700"
            >
              {STYLE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          )}
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Mobile First</label>
        <Controller
          control={control}
          name="mobileFirst"
          render={({ field }) => (
            <button
              type="button"
              onClick={() => field.onChange(!field.value)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                field.value ? 'bg-cyan-600' : 'bg-slate-700'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  field.value ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          )}
        />
      </div>
    </div>
  )
}
