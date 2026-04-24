import type { IntakeFormValues } from '@/lib/schemas/intake-form'

// Target type matches CustomerConfig backend schema exactly
export interface CustomerConfig {
  business_context: {
    company_name: string
    industry: string
    business_size: string
    target_users: string[]
  }
  problem_statement: {
    current_situation: string
    desired_outcome: string
    pain_points: string[]
  }
  features: {
    must_have: Array<{ name: string; description: string; priority: number }>
    nice_to_have: string[]
  }
  data_requirements: {
    data_types: string[]
    file_uploads: never[]
    data_volume: string
    external_integrations: string[]
  }
  design_preferences: {
    visual_style: string
    color_preferences: string[]
    mobile_support: string
    accessibility_requirements: string[]
    example_sites: string[]
  }
  technical_requirements: {
    access_scope: string
    performance_requirements: string[]
    security_requirements: string[]
    compliance_requirements: never[]
  }
  project_meta: {
    project_name: string
    deadline: string | null
    budget_range: string | null
    additional_context: string | null
  }
}

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
  return {
    business_context: {
      company_name: form.companyName,
      industry: INDUSTRY_MAP[form.industry] ?? form.industry,
      business_size: BUSINESS_SIZE_MAP[form.businessSize] ?? form.businessSize,
      target_users: form.targetUsers.map(u => USER_TYPE_MAP[u] ?? u),
    },
    problem_statement: {
      current_situation: form.currentSituation,
      desired_outcome: form.desiredOutcome,
      pain_points: form.painPoints,
    },
    features: {
      must_have: form.mustHaveFeatures.map(f => ({
        name: f.name,
        description: f.description,
        priority: f.priority,
      })),
      nice_to_have: form.niceToHaveFeatures,
    },
    data_requirements: {
      data_types: form.dataTypes,
      file_uploads: [],
      data_volume: DATA_VOLUME_MAP[form.dataVolume] ?? form.dataVolume,
      external_integrations: form.externalIntegrations,
    },
    design_preferences: {
      visual_style: VISUAL_STYLE_MAP[form.visualStyle] ?? form.visualStyle,
      color_preferences: form.colorPreferences,
      mobile_support: MOBILE_SUPPORT_MAP[form.mobileSupport] ?? form.mobileSupport,
      accessibility_requirements: form.accessibilityRequirements,
      example_sites: form.exampleSites,
    },
    technical_requirements: {
      access_scope: ACCESS_SCOPE_MAP[form.accessScope] ?? form.accessScope,
      performance_requirements: form.performanceRequirements,
      security_requirements: form.securityRequirements,
      compliance_requirements: [],
    },
    project_meta: {
      project_name: form.projectName,
      deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
      budget_range: form.budgetRange,
      additional_context: form.additionalContext,
    },
  }
}
