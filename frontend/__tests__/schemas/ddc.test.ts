import { CustomerConfigV2Schema, DDC_SCHEMA_VERSION } from '@/lib/schemas/ddc'
import goldenFixture from '../fixtures/ddc_ecommerce.json'

describe('CustomerConfigV2Schema — golden fixture', () => {
  test('validates the e-commerce DDC fixture without errors', () => {
    const result = CustomerConfigV2Schema.safeParse(goldenFixture)
    expect(result.success).toBe(true)
  })

  test('parsed fixture has correct schema_version', () => {
    const result = CustomerConfigV2Schema.parse(goldenFixture)
    expect(result.schema_version).toBe(DDC_SCHEMA_VERSION)
  })

  test('parsed fixture has correct project name', () => {
    const result = CustomerConfigV2Schema.parse(goldenFixture)
    expect(result.context.name).toBe('shopflow')
  })

  test('parsed fixture has two actors', () => {
    const result = CustomerConfigV2Schema.parse(goldenFixture)
    expect(result.actors).toHaveLength(2)
  })

  test('parsed fixture has three entities', () => {
    const result = CustomerConfigV2Schema.parse(goldenFixture)
    expect(result.entities).toHaveLength(3)
  })

  test('parsed fixture has five use cases', () => {
    const result = CustomerConfigV2Schema.parse(goldenFixture)
    expect(result.use_cases).toHaveLength(5)
  })

  test('parsed fixture has three business rules', () => {
    const result = CustomerConfigV2Schema.parse(goldenFixture)
    expect(result.business_rules).toHaveLength(3)
  })

  test('parsed fixture has two relationships', () => {
    const result = CustomerConfigV2Schema.parse(goldenFixture)
    expect(result.relationships).toHaveLength(2)
  })
})

describe('CustomerConfigV2Schema — enum validation', () => {
  const base = CustomerConfigV2Schema.parse(goldenFixture)

  test('rejects invalid industry', () => {
    const result = CustomerConfigV2Schema.safeParse({
      ...goldenFixture,
      context: { ...goldenFixture.context, industry: 'bad_industry' },
    })
    expect(result.success).toBe(false)
  })

  test('rejects invalid visual_style', () => {
    const result = CustomerConfigV2Schema.safeParse({
      ...goldenFixture,
      context: { ...goldenFixture.context, visual_style: 'ugly' },
    })
    expect(result.success).toBe(false)
  })

  test('rejects invalid auth_method', () => {
    const actors = goldenFixture.actors.map((a, i) =>
      i === 0 ? { ...a, auth_method: 'biometric' } : a
    )
    const result = CustomerConfigV2Schema.safeParse({ ...goldenFixture, actors })
    expect(result.success).toBe(false)
  })

  test('rejects invalid use_case type', () => {
    const use_cases = goldenFixture.use_cases.map((u, i) =>
      i === 0 ? { ...u, type: 'mutation' } : u
    )
    const result = CustomerConfigV2Schema.safeParse({ ...goldenFixture, use_cases })
    expect(result.success).toBe(false)
  })
})

describe('CustomerConfigV2Schema — string constraints', () => {
  test('rejects domain_description shorter than 50 chars', () => {
    const result = CustomerConfigV2Schema.safeParse({
      ...goldenFixture,
      context: { ...goldenFixture.context, domain_description: 'Too short.' },
    })
    expect(result.success).toBe(false)
  })

  test('rejects actor role_name not in PascalCase', () => {
    const actors = goldenFixture.actors.map((a, i) =>
      i === 0 ? { ...a, role_name: 'customer' } : a
    )
    const result = CustomerConfigV2Schema.safeParse({ ...goldenFixture, actors })
    expect(result.success).toBe(false)
  })

  test('rejects entity attribute name with spaces', () => {
    const entities = goldenFixture.entities.map((e, i) => {
      if (i !== 0) return e
      const attrs = e.attributes.map((a, j) =>
        j === 0 ? { ...a, name: 'bad name' } : a
      )
      return { ...e, attributes: attrs }
    })
    const result = CustomerConfigV2Schema.safeParse({ ...goldenFixture, entities })
    expect(result.success).toBe(false)
  })
})

describe('CustomerConfigV2Schema — minimum cardinality', () => {
  test('rejects empty actors array', () => {
    const result = CustomerConfigV2Schema.safeParse({ ...goldenFixture, actors: [] })
    expect(result.success).toBe(false)
  })

  test('rejects empty entities array', () => {
    const result = CustomerConfigV2Schema.safeParse({ ...goldenFixture, entities: [] })
    expect(result.success).toBe(false)
  })

  test('rejects empty use_cases array', () => {
    const result = CustomerConfigV2Schema.safeParse({ ...goldenFixture, use_cases: [] })
    expect(result.success).toBe(false)
  })
})
