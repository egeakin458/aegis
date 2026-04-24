import { mapFormToCustomerConfig } from '@/lib/mappers/config'
import { intakeFormDefaults } from '@/lib/schemas/intake-form'

const BASE = {
  ...intakeFormDefaults,
  companyName: 'Acme',
  currentSituation: 'We do everything manually',
  desiredOutcome: 'We want automation',
  mustHaveFeatures: [{ id: '1', name: 'Dashboard', description: '', priority: 1 }],
  projectName: 'AcmeApp',
}

describe('mapFormToCustomerConfig — enum round-trips', () => {
  test.each([
    ['1–5', '1-5'],
    ['6–20', '6-20'],
    ['21–50', '21-50'],
    ['50+', '50+'],
  ])('businessSize %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, businessSize: input as any })
    expect(result.business_context.business_size).toBe(expected)
  })

  test.each([
    ['Retail', 'retail'],
    ['Food & Beverage', 'food_and_beverage'],
    ['Professional Services', 'professional_services'],
    ['Healthcare', 'healthcare'],
    ['Education', 'education'],
    ['Manufacturing', 'manufacturing'],
    ['Other', 'other'],
  ])('industry %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, industry: input as any })
    expect(result.business_context.industry).toBe(expected)
  })

  test.each([
    [['Owner'], ['owner']],
    [['Employees'], ['employees']],
    [['Customers'], ['customers']],
    [['All Users'], ['all']],
    [['Owner', 'Customers'], ['owner', 'customers']],
  ])('targetUsers %j → %j', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, targetUsers: input as any })
    expect(result.business_context.target_users).toEqual(expected)
  })

  test.each([
    ['Under 100', 'under_100'],
    ['100–1,000', '100-1000'],
    ['1,000–10,000', '1000-10000'],
    ['10,000+', '10000+'],
  ])('dataVolume %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, dataVolume: input as any })
    expect(result.data_requirements.data_volume).toBe(expected)
  })

  test.each([
    ['Clean & Minimal', 'clean_minimal'],
    ['Professional & Corporate', 'professional_corporate'],
    ['Modern & Colorful', 'modern_colorful'],
    ['No Preference', 'no_preference'],
  ])('visualStyle %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, visualStyle: input as any })
    expect(result.design_preferences.visual_style).toBe(expected)
  })

  test.each([
    ['Yes', 'yes'],
    ['No', 'no'],
    ['Nice to Have', 'nice_to_have'],
  ])('mobileSupport %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, mobileSupport: input as any })
    expect(result.design_preferences.mobile_support).toBe(expected)
  })

  test.each([
    ['Just Me', 'just_me'],
    ['Team / Network', 'team_network'],
    ['Anyone on the Internet', 'anyone_internet'],
  ])('accessScope %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, accessScope: input as any })
    expect(result.technical_requirements.access_scope).toBe(expected)
  })

  test('deadline ISO conversion', () => {
    const result = mapFormToCustomerConfig({ ...BASE, deadline: '2026-06-01' })
    expect(result.project_meta.deadline).toMatch(/^2026-06-01T/)
  })

  test('null deadline stays null', () => {
    const result = mapFormToCustomerConfig({ ...BASE, deadline: null })
    expect(result.project_meta.deadline).toBeNull()
  })

  test('file_uploads always empty array', () => {
    const result = mapFormToCustomerConfig(BASE)
    expect(result.data_requirements.file_uploads).toEqual([])
  })
})
