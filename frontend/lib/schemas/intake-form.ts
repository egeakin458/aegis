import { z } from 'zod'

export const featureSchema = z.object({
  id: z.string(),
  name: z.string().min(1, 'Feature name required'),
  description: z.string().default(''),
  priority: z.number().int().min(1),
})

export type FeatureItem = z.infer<typeof featureSchema>

export const intakeFormSchema = z.object({
  // Section 1: Business Context
  companyName: z.string().min(1, 'Company name is required'),
  industry: z.enum(['Retail', 'Food & Beverage', 'Professional Services', 'Healthcare', 'Education', 'Manufacturing', 'Other']),
  businessSize: z.enum(['1–5', '6–20', '21–50', '50+']),
  targetUsers: z.array(z.enum(['Owner', 'Employees', 'Customers', 'All Users'])).min(1, 'Select at least one user type'),

  // Section 2: Problem Statement
  currentSituation: z.string().min(10, 'Please describe your current situation'),
  desiredOutcome: z.string().min(10, 'Please describe the desired outcome'),
  painPoints: z.array(z.string()).default([]),

  // Section 3: Features
  mustHaveFeatures: z.array(featureSchema).min(1, 'Add at least one feature'),
  niceToHaveFeatures: z.array(z.string()).default([]),

  // Section 4: Data & Content
  dataTypes: z.array(z.string()).default([]),
  dataVolume: z.enum(['Under 100', '100–1,000', '1,000–10,000', '10,000+']),
  externalIntegrations: z.array(z.string()).default([]),

  // Section 5: Design
  visualStyle: z.enum(['Clean & Minimal', 'Professional & Corporate', 'Modern & Colorful', 'No Preference']),
  colorPreferences: z.array(z.string()).default([]),
  mobileSupport: z.enum(['Yes', 'No', 'Nice to Have']),
  accessibilityRequirements: z.array(z.string()).default([]),
  exampleSites: z.array(z.string()).default([]),

  // Section 6: Technical
  accessScope: z.enum(['Just Me', 'Team / Network', 'Anyone on the Internet']),
  performanceRequirements: z.array(z.string()).default([]),
  securityRequirements: z.array(z.string()).default([]),

  // Section 7: Timeline & Meta
  projectName: z.string().min(1, 'Project name is required'),
  deadline: z.string().nullable().default(null),
  budgetRange: z.string().nullable().default(null),
  additionalContext: z.string().nullable().default(null),
})

export type IntakeFormValues = z.infer<typeof intakeFormSchema>
export type IntakeFormInput = z.input<typeof intakeFormSchema>

// Type for react-hook-form's UseFormReturn shared across sections.
// We use the schema output (IntakeFormValues) for both input and output, so form
// values are non-optional inside section components (defaults are supplied via
// intakeFormDefaults). The resolver is cast at the useForm call site.
export type IntakeFormReturn = import('react-hook-form').UseFormReturn<IntakeFormValues>

export const intakeFormDefaults: IntakeFormValues = {
  companyName: '',
  industry: 'Retail',
  businessSize: '1–5',
  targetUsers: [],
  currentSituation: '',
  desiredOutcome: '',
  painPoints: [],
  mustHaveFeatures: [],
  niceToHaveFeatures: [],
  dataTypes: [],
  dataVolume: 'Under 100',
  externalIntegrations: [],
  visualStyle: 'Clean & Minimal',
  colorPreferences: [],
  mobileSupport: 'Yes',
  accessibilityRequirements: [],
  exampleSites: [],
  accessScope: 'Just Me',
  performanceRequirements: [],
  securityRequirements: [],
  projectName: '',
  deadline: null,
  budgetRange: null,
  additionalContext: null,
}
