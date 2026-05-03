import { mapFormToDDC } from '@/lib/mappers/config'
import { CustomerConfigV2Schema } from '@/lib/schemas/ddc'
import { freeTextFormDefaults } from '@/lib/schemas/intake-form'

// Long-enough domain description to satisfy the 50-char minimum
const LONG_DESC =
  'An online retail store where customers browse products and place orders.'

const BASE = {
  ...freeTextFormDefaults,
  projectName: 'acme-shop',
  domainDescription: LONG_DESC,
}

describe('mapFormToDDC — output validates as CustomerConfigV2', () => {
  test('valid input produces a passing CustomerConfigV2', () => {
    const result = CustomerConfigV2Schema.safeParse(mapFormToDDC(BASE))
    expect(result.success).toBe(true)
  })

  test('schema_version is always ddc-v1', () => {
    expect(mapFormToDDC(BASE).schema_version).toBe('ddc-v1')
  })
})

describe('mapFormToDDC — industry pass-through (no transformation)', () => {
  test.each([
    'retail',
    'healthcare',
    'education',
    'finance',
    'services',
    'other',
  ] as const)('industry %s passes through unchanged', (industry) => {
    const ddc = mapFormToDDC({ ...BASE, industry })
    expect(ddc.context.industry).toBe(industry)
  })
})

describe('mapFormToDDC — visual style pass-through', () => {
  test.each([
    'clean_minimal',
    'bold_modern',
    'warm_friendly',
    'professional_corporate',
    'playful',
  ] as const)('visual_style %s passes through unchanged', (visualStyle) => {
    const ddc = mapFormToDDC({ ...BASE, visualStyle })
    expect(ddc.context.visual_style).toBe(visualStyle)
  })
})

describe('mapFormToDDC — project name conversion', () => {
  test.each([
    ['shopflow', 'shopflow'],
    ['My Shop', 'my-shop'],
    ['Acme Inc.', 'acme-inc'],
    ['task manager', 'task-manager'],
  ])('projectName %s → context.name %s', (projectName, expected) => {
    const ddc = mapFormToDDC({ ...BASE, projectName })
    expect(ddc.context.name).toBe(expected)
  })
})

describe('mapFormToDDC — mobile_first boolean', () => {
  test('mobileFirst true → context.mobile_first true', () => {
    const ddc = mapFormToDDC({ ...BASE, mobileFirst: true })
    expect(ddc.context.mobile_first).toBe(true)
  })

  test('mobileFirst false → context.mobile_first false', () => {
    const ddc = mapFormToDDC({ ...BASE, mobileFirst: false })
    expect(ddc.context.mobile_first).toBe(false)
  })
})

describe('mapFormToDDC — domain description', () => {
  test('domain description is passed through unchanged', () => {
    const ddc = mapFormToDDC({ ...BASE, domainDescription: LONG_DESC })
    expect(ddc.context.domain_description).toBe(LONG_DESC)
  })
})

describe('mapFormToDDC — placeholder DDC structure', () => {
  test('produces exactly one placeholder actor', () => {
    const ddc = mapFormToDDC(BASE)
    expect(ddc.actors).toHaveLength(1)
  })

  test('produces exactly one placeholder entity', () => {
    const ddc = mapFormToDDC(BASE)
    expect(ddc.entities).toHaveLength(1)
  })

  test('produces exactly one placeholder use case', () => {
    const ddc = mapFormToDDC(BASE)
    expect(ddc.use_cases).toHaveLength(1)
  })

  test('placeholder actor uses anonymous auth', () => {
    const ddc = mapFormToDDC(BASE)
    expect(ddc.actors[0].auth_method).toBe('anonymous')
  })

  test('placeholder use case actor_id matches placeholder actor', () => {
    const ddc = mapFormToDDC(BASE)
    expect(ddc.use_cases[0].actor_id).toBe(ddc.actors[0].id)
  })

  test('placeholder use case primary_entity_id matches placeholder entity', () => {
    const ddc = mapFormToDDC(BASE)
    expect(ddc.use_cases[0].primary_entity_id).toBe(ddc.entities[0].id)
  })

  test('no hardcoded auth_required field in output', () => {
    const ddc = mapFormToDDC(BASE)
    expect(ddc).not.toHaveProperty('auth_required')
  })

  test('no string concatenation artifacts in description', () => {
    const ddc = mapFormToDDC(BASE)
    const actorDesc = ddc.actors[0].permissions_description
    expect(actorDesc).not.toContain('undefined')
    expect(actorDesc).not.toContain('null')
  })
})
