import { mapFreeTextToDDC } from '@/lib/mappers/free-text'
import { CustomerConfigV2Schema } from '@/lib/schemas/ddc'
import { freeTextFormDefaults } from '@/lib/schemas/intake-form'

const BASE_INPUT = {
  ...freeTextFormDefaults,
  projectName: 'shopflow',
  domainDescription:
    'An online retail store where customers can browse products, add them to a cart, and place orders. Admins manage the product catalog and monitor all orders.',
}

describe('mapFreeTextToDDC — produces a valid CustomerConfigV2', () => {
  test('output passes CustomerConfigV2Schema validation', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    const result = CustomerConfigV2Schema.safeParse(ddc)
    expect(result.success).toBe(true)
  })

  test('schema_version is ddc-v1', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.schema_version).toBe('ddc-v1')
  })

  test('context.name is kebab-case project name', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.context.name).toBe('shopflow')
  })

  test('context.domain_description matches input', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.context.domain_description).toBe(BASE_INPUT.domainDescription)
  })

  test('context.industry matches input', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.context.industry).toBe('retail')
  })

  test('context.visual_style matches input', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.context.visual_style).toBe('clean_minimal')
  })

  test('context.mobile_first matches input', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.context.mobile_first).toBe(true)
  })

  test('has exactly one placeholder actor', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.actors).toHaveLength(1)
  })

  test('has exactly one placeholder entity', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.entities).toHaveLength(1)
  })

  test('has exactly one placeholder use case', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.use_cases).toHaveLength(1)
  })

  test('use case actor_id references the placeholder actor', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.use_cases[0].actor_id).toBe(ddc.actors[0].id)
  })

  test('use case primary_entity_id references the placeholder entity', () => {
    const ddc = mapFreeTextToDDC(BASE_INPUT)
    expect(ddc.use_cases[0].primary_entity_id).toBe(ddc.entities[0].id)
  })

  test('project name with spaces is converted to kebab-case', () => {
    const ddc = mapFreeTextToDDC({ ...BASE_INPUT, projectName: 'My Cool App' })
    expect(ddc.context.name).toBe('my-cool-app')
  })

  test('mobile_first false is preserved', () => {
    const ddc = mapFreeTextToDDC({ ...BASE_INPUT, mobileFirst: false })
    expect(ddc.context.mobile_first).toBe(false)
  })
})
