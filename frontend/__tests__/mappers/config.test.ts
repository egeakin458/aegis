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
    const result = mapFormToCustomerConfig({ ...BASE, businessSize: input as never })
    expect(result.business_context.size).toBe(expected)
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
    const result = mapFormToCustomerConfig({ ...BASE, industry: input as never })
    expect(result.business_context.industry).toBe(expected)
  })

  test.each([
    [['Owner'], ['owner']],
    [['Employees'], ['employees']],
    [['Customers'], ['customers']],
    [['All Users'], ['all']],
    [['Owner', 'Customers'], ['owner', 'customers']],
  ])('targetUsers %j → %j', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, targetUsers: input as never })
    expect(result.problem_statement.users).toEqual(expected)
  })

  test.each([
    ['Under 100', 'under_100'],
    ['100–1,000', '100-1000'],
    ['1,000–10,000', '1000-10000'],
    ['10,000+', '10000+'],
  ])('dataVolume %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, dataVolume: input as never })
    expect(result.data.volume).toBe(expected)
  })

  test.each([
    ['Clean & Minimal', 'clean_minimal'],
    ['Professional & Corporate', 'professional_corporate'],
    ['Modern & Colorful', 'modern_colorful'],
    ['No Preference', 'no_preference'],
  ])('visualStyle %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, visualStyle: input as never })
    expect(result.design.style).toBe(expected)
  })

  test.each([
    ['Yes', 'yes'],
    ['No', 'no'],
    ['Nice to Have', 'nice_to_have'],
  ])('mobileSupport %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, mobileSupport: input as never })
    expect(result.technical.mobile).toBe(expected)
  })

  test.each([
    ['Just Me', 'just_me'],
    ['Team / Network', 'team_network'],
    ['Anyone on the Internet', 'anyone_internet'],
  ])('accessScope %s → %s', (input, expected) => {
    const result = mapFormToCustomerConfig({ ...BASE, accessScope: input as never })
    expect(result.technical.access_scope).toBe(expected)
  })

  test('deadline ISO conversion', () => {
    const result = mapFormToCustomerConfig({ ...BASE, deadline: '2026-06-01' })
    expect(result.meta.deadline).toMatch(/^2026-06-01T/)
  })

  test('null deadline stays null', () => {
    const result = mapFormToCustomerConfig({ ...BASE, deadline: null })
    expect(result.meta.deadline).toBeNull()
  })

  test('uploads always empty array', () => {
    const result = mapFormToCustomerConfig(BASE)
    expect(result.data.uploads).toEqual([])
  })

  test('mustHaveFeatures mapped to features.requested', () => {
    const result = mapFormToCustomerConfig({
      ...BASE,
      mustHaveFeatures: [{ id: '1', name: 'Login', description: 'User login', priority: 1 }],
    })
    expect(result.features.requested[0].description).toContain('Login')
    expect(result.features.requested[0].priority).toBe(1)
  })

  test('niceToHaveFeatures appended after mustHave with higher priority', () => {
    const result = mapFormToCustomerConfig({
      ...BASE,
      mustHaveFeatures: [{ id: '1', name: 'Login', description: '', priority: 1 }],
      niceToHaveFeatures: ['Dark mode'],
    })
    expect(result.features.requested).toHaveLength(2)
    expect(result.features.requested[1].description).toBe('Dark mode')
    expect(result.features.requested[1].priority).toBeGreaterThan(result.features.requested[0].priority)
  })
})
