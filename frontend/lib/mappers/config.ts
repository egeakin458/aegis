import type { IntakeFormValues } from '@/lib/schemas/intake-form'
import type {
  CustomerConfig,
  IndustryType,
  BusinessSize,
  UserType,
  DataVolume,
  DesignStyle,
  MobileSupport,
  AccessScope,
} from '@/lib/types/api'

const INDUSTRY_MAP: Record<string, string> = {
  'Retail': 'retail',
  'Food & Beverage': 'food_and_beverage',
  'Professional Services': 'professional_services',
  'Healthcare': 'healthcare',
  'Education': 'education',
  'Manufacturing': 'manufacturing',
  'Other': 'other',
}

const BUSINESS_SIZE_MAP: Record<string, string> = {
  '1–5': '1-5',
  '6–20': '6-20',
  '21–50': '21-50',
  '50+': '50+',
}

const USER_TYPE_MAP: Record<string, string> = {
  'Owner': 'owner',
  'Employees': 'employees',
  'Customers': 'customers',
  'All Users': 'all',
}

const DATA_VOLUME_MAP: Record<string, string> = {
  'Under 100': 'under_100',
  '100–1,000': '100-1000',
  '1,000–10,000': '1000-10000',
  '10,000+': '10000+',
}

const VISUAL_STYLE_MAP: Record<string, string> = {
  'Clean & Minimal': 'clean_minimal',
  'Professional & Corporate': 'professional_corporate',
  'Modern & Colorful': 'modern_colorful',
  'No Preference': 'no_preference',
}

const MOBILE_SUPPORT_MAP: Record<string, string> = {
  'Yes': 'yes',
  'No': 'no',
  'Nice to Have': 'nice_to_have',
}

const ACCESS_SCOPE_MAP: Record<string, string> = {
  'Just Me': 'just_me',
  'Team / Network': 'team_network',
  'Anyone on the Internet': 'anyone_internet',
}

export function mapFormToCustomerConfig(form: IntakeFormValues): CustomerConfig {
  const mustHave = form.mustHaveFeatures.map((f, i) => ({
    description: f.name + (f.description ? ': ' + f.description : ''),
    priority: f.priority ?? i + 1,
  }))
  const niceToHave = form.niceToHaveFeatures.map((desc, i) => ({
    description: desc,
    priority: mustHave.length + i + 1,
  }))

  const entityParts: string[] = []
  if (form.dataTypes.length > 0) entityParts.push(form.dataTypes.join(', '))
  if (form.externalIntegrations.length > 0) entityParts.push('integrations: ' + form.externalIntegrations.join(', '))
  const entities = entityParts.length > 0 ? entityParts.join('; ') : 'Application data'

  const painPointsStr = form.painPoints.length > 0 ? form.painPoints.join('. ') : null

  return {
    business_context: {
      name: form.companyName,
      industry: (INDUSTRY_MAP[form.industry] ?? form.industry) as IndustryType,
      industry_other: form.industry === 'Other' ? form.companyName : null,
      description: form.currentSituation,
      size: (BUSINESS_SIZE_MAP[form.businessSize] ?? form.businessSize) as BusinessSize,
    },
    problem_statement: {
      problem: [form.currentSituation, form.desiredOutcome].filter(Boolean).join(' → '),
      users: form.targetUsers.map(u => (USER_TYPE_MAP[u] ?? u) as UserType),
      current_process: painPointsStr,
    },
    features: {
      requested: [...mustHave, ...niceToHave],
    },
    data: {
      entities,
      has_existing_data: false,
      uploads: [],
      volume: (DATA_VOLUME_MAP[form.dataVolume] ?? form.dataVolume) as DataVolume,
    },
    design: {
      colors: form.colorPreferences.length > 0 ? form.colorPreferences : null,
      logo: null,
      references: [],
      style: (VISUAL_STYLE_MAP[form.visualStyle] ?? form.visualStyle) as DesignStyle,
    },
    technical: {
      access_scope: (ACCESS_SCOPE_MAP[form.accessScope] ?? form.accessScope) as AccessScope,
      auth_required: true,
      user_roles: null,
      mobile: (MOBILE_SUPPORT_MAP[form.mobileSupport] ?? form.mobileSupport) as MobileSupport,
    },
    meta: {
      deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
      notes: form.additionalContext ?? null,
      submitted_at: new Date().toISOString(),
    },
  }
}
