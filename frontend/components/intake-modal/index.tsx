'use client'
import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { X } from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { FreeTextSection } from './sections/free-text'
import { ActorsSection } from './sections/actors'
import { EntitiesSection } from './sections/entities'
import { RelationshipsSection } from './sections/relationships'
import { BusinessRulesSection } from './sections/rules'
import { UseCasesSection } from './sections/use-cases'
import { freeTextFormSchema, freeTextFormDefaults, type FreeTextFormValues } from '@/lib/schemas/intake-form'
import { CustomerConfigV2Schema, type CustomerConfigV2 } from '@/lib/schemas/ddc'
import { mapFreeTextToDDC } from '@/lib/mappers/free-text'

type IntakeMode = 'free-text' | 'structured'
const MODE_KEY = 'aegis_intake_mode'

const STRUCTURED_SECTIONS = ['Actors', 'Entities', 'Relationships', 'Rules', 'Use Cases']

interface Props {
  open: boolean
  onClose: () => void
  onSubmit?: (config: CustomerConfigV2) => void
}

export function IntakeModal({ open, onClose, onSubmit }: Props) {
  const [section, setSection] = useState(0)
  const [mode, setMode] = useState<IntakeMode>('free-text')

  // Persist mode choice
  useEffect(() => {
    const stored = localStorage.getItem(MODE_KEY)
    if (stored === 'free-text' || stored === 'structured') setMode(stored)
  }, [])
  function switchMode(m: IntakeMode) {
    setMode(m)
    localStorage.setItem(MODE_KEY, m)
    setSection(0)
  }

  // Free-text DDC form
  const freeTextForm = useForm<FreeTextFormValues>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(freeTextFormSchema) as any,
    defaultValues: freeTextFormDefaults,
    mode: 'onTouched',
  })

  // Structured DDC form
  const structuredForm = useForm<CustomerConfigV2>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(CustomerConfigV2Schema) as any,
    defaultValues: {
      schema_version: 'ddc-v1',
      context: { name: '', domain_description: '', industry: 'retail', visual_style: 'clean_minimal', mobile_first: true },
      actors: [],
      entities: [],
      relationships: [],
      business_rules: [],
      use_cases: [],
    },
    mode: 'onTouched',
  })

  async function handleNext() {
    if (mode === 'structured') {
      setSection(s => Math.min(STRUCTURED_SECTIONS.length - 1, s + 1))
    }
  }

  function handleFreeTextSubmit(values: FreeTextFormValues) {
    const ddc = mapFreeTextToDDC(values)
    console.log('[IntakeModal] DDC (free-text):', JSON.stringify(ddc, null, 2))
    onSubmit?.(ddc as CustomerConfigV2)
    onClose()
  }

  function handleStructuredSubmit(values: CustomerConfigV2) {
    console.log('[IntakeModal] DDC (structured):', JSON.stringify(values, null, 2))
    onSubmit?.(values)
    onClose()
  }

  function handleClose() {
    freeTextForm.reset()
    setSection(0)
    onClose()
  }

  const currentSections = mode === 'structured' ? STRUCTURED_SECTIONS : ['Quick']
  const maxSection = currentSections.length - 1

  return (
    <Dialog open={open} onOpenChange={v => !v && handleClose()}>
      <DialogContent className="max-w-2xl bg-[#0f1729] border-slate-700 text-slate-200 p-0 overflow-hidden max-h-[90vh] flex flex-col">
        {/* Progress bar */}
        <div className="h-1 bg-slate-800 shrink-0">
          <div
            className="h-full bg-[#22d3ee] transition-all duration-300"
            style={{ width: `${((section + 1) / currentSections.length) * 100}%` }}
          />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 shrink-0">
          <div>
            <h2 className="text-base font-semibold">New Project</h2>
            <p className="text-xs text-slate-400">{section + 1} / {currentSections.length} — {currentSections[section]}</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Mode toggle */}
            <div className="flex gap-1 text-xs">
              {(['free-text', 'structured'] as IntakeMode[]).map(m => (
                <button
                  key={m}
                  type="button"
                  onClick={() => switchMode(m)}
                  className={`px-2 py-1 rounded transition-colors ${
                    mode === m ? 'bg-slate-700 text-slate-200' : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {m === 'free-text' ? 'Quick' : 'Advanced'}
                </button>
              ))}
            </div>
            <button onClick={handleClose} className="text-slate-500 hover:text-slate-300 transition-colors">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Section tabs (structured only) */}
        {mode === 'structured' && (
          <div className="flex gap-1 px-6 pt-4 flex-wrap shrink-0">
            {currentSections.map((s, i) => (
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
        )}

        {/* Section content — free-text DDC */}
        {mode === 'free-text' && (
          <form
            onSubmit={freeTextForm.handleSubmit(handleFreeTextSubmit)}
            className="flex-1 overflow-y-auto px-6 py-5"
          >
            <FreeTextSection form={freeTextForm} />
          </form>
        )}

        {/* Section content — structured DDC */}
        {mode === 'structured' && (
          <form
            onSubmit={structuredForm.handleSubmit(handleStructuredSubmit)}
            className="flex-1 overflow-y-auto px-6 py-5"
          >
            {section === 0 && <ActorsSection form={structuredForm} />}
            {section === 1 && <EntitiesSection form={structuredForm} />}
            {section === 2 && <RelationshipsSection form={structuredForm} />}
            {section === 3 && <BusinessRulesSection form={structuredForm} />}
            {section === 4 && <UseCasesSection form={structuredForm} />}
          </form>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 shrink-0">
          <button
            type="button"
            onClick={() => setSection(s => Math.max(0, s - 1))}
            disabled={section === 0 || mode === 'free-text'}
            className="px-4 py-2 text-sm rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 disabled:opacity-40 transition-colors"
          >
            Back
          </button>
          {(mode === 'structured' && section < maxSection) ? (
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
              onClick={
                mode === 'free-text'
                  ? freeTextForm.handleSubmit(handleFreeTextSubmit)
                  : structuredForm.handleSubmit(handleStructuredSubmit)
              }
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
