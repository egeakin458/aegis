'use client'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { X } from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { BusinessContextSection } from './sections/business-context'
import { ProblemStatementSection } from './sections/problem-statement'
import { FeaturesSection } from './sections/features'
import { DataContentSection } from './sections/data-content'
import { DesignSection } from './sections/design'
import { TechnicalSection } from './sections/technical'
import { TimelineSection } from './sections/timeline'
import { intakeFormSchema, intakeFormDefaults, type IntakeFormValues } from '@/lib/schemas/intake-form'
import { mapFormToCustomerConfig } from '@/lib/mappers/config'

const SECTIONS = [
  'Business Context',
  'Problem Statement',
  'Features',
  'Data & Content',
  'Design',
  'Technical',
  'Timeline',
]

// Which fields belong to each section (for per-section validation trigger)
const SECTION_FIELDS: (keyof IntakeFormValues)[][] = [
  ['companyName', 'industry', 'businessSize', 'targetUsers'],
  ['currentSituation', 'desiredOutcome'],
  ['mustHaveFeatures'],
  ['dataTypes', 'dataVolume'],
  ['visualStyle', 'mobileSupport'],
  ['accessScope'],
  ['projectName'],
]

interface Props {
  open: boolean
  onClose: () => void
  onSubmit?: (config: ReturnType<typeof mapFormToCustomerConfig>) => void
}

export function IntakeModal({ open, onClose, onSubmit }: Props) {
  const [section, setSection] = useState(0)

  const form = useForm<IntakeFormValues>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(intakeFormSchema) as any,
    defaultValues: intakeFormDefaults,
    mode: 'onTouched',
  })

  async function handleNext() {
    const fields = SECTION_FIELDS[section]
    const valid = await form.trigger(fields)
    if (valid) setSection(s => Math.min(SECTIONS.length - 1, s + 1))
  }

  function handleSubmit(values: IntakeFormValues) {
    const config = mapFormToCustomerConfig(values)
    console.log('[IntakeModal] CustomerConfig:', JSON.stringify(config, null, 2))
    onSubmit?.(config)
    onClose()
  }

  function handleClose() {
    form.reset()
    setSection(0)
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={v => !v && handleClose()}>
      <DialogContent className="max-w-2xl bg-[#0f1729] border-slate-700 text-slate-200 p-0 overflow-hidden max-h-[90vh] flex flex-col">
        {/* Progress bar */}
        <div className="h-1 bg-slate-800 shrink-0">
          <div
            className="h-full bg-[#22d3ee] transition-all duration-300"
            style={{ width: `${((section + 1) / SECTIONS.length) * 100}%` }}
          />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 shrink-0">
          <div>
            <h2 className="text-base font-semibold">New Project</h2>
            <p className="text-xs text-slate-400">{section + 1} / {SECTIONS.length} — {SECTIONS[section]}</p>
          </div>
          <button onClick={handleClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Section tabs */}
        <div className="flex gap-1 px-6 pt-4 flex-wrap shrink-0">
          {SECTIONS.map((s, i) => (
            <button
              key={s}
              type="button"
              onClick={() => setSection(i)}
              className={`text-xs px-3 py-1 rounded-full transition-colors ${
                i === section
                  ? 'bg-[#22d3ee] text-[#0f172a] font-medium'
                  : i < section
                  ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-300'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Section content */}
        <form
          onSubmit={form.handleSubmit(handleSubmit)}
          className="flex-1 overflow-y-auto px-6 py-5"
        >
          {section === 0 && <BusinessContextSection form={form} />}
          {section === 1 && <ProblemStatementSection form={form} />}
          {section === 2 && <FeaturesSection form={form} />}
          {section === 3 && <DataContentSection form={form} />}
          {section === 4 && <DesignSection form={form} />}
          {section === 5 && <TechnicalSection form={form} />}
          {section === 6 && <TimelineSection form={form} />}
        </form>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 shrink-0">
          <button
            type="button"
            onClick={() => setSection(s => Math.max(0, s - 1))}
            disabled={section === 0}
            className="px-4 py-2 text-sm rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 disabled:opacity-40 transition-colors"
          >
            Back
          </button>
          {section < SECTIONS.length - 1 ? (
            <button
              type="button"
              onClick={handleNext}
              className="px-4 py-2 text-sm rounded-lg bg-[#22d3ee] text-[#0f172a] font-medium hover:bg-cyan-300 transition-colors"
            >
              Next
            </button>
          ) : (
            <button
              type="button"
              onClick={form.handleSubmit(handleSubmit)}
              className="px-4 py-2 text-sm rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-500 transition-colors"
            >
              Start Pipeline
            </button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
