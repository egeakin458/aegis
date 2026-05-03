/**
 * Structured DDC intake mode — happy-path validation tests.
 *
 * These tests verify that a complete structured DDC payload (as would be
 * produced by the structured builder form) passes CustomerConfigV2Schema
 * validation. We test the data layer, not the React rendering.
 */

import { CustomerConfigV2Schema } from '@/lib/schemas/ddc'

const HAPPY_PATH_DDC = {
  schema_version: 'ddc-v1',
  context: {
    name: 'shopflow',
    domain_description:
      'An online retail store where customers can browse products, add them to a cart, and place orders. Admins manage the product catalog and monitor all orders.',
    industry: 'retail',
    visual_style: 'clean_minimal',
    mobile_first: true,
  },
  actors: [
    {
      id: 'act_cust0001',
      role_name: 'Customer',
      auth_method: 'email_password',
      permissions_description: 'Can browse products, add items to cart, and place orders.',
    },
    {
      id: 'act_admin001',
      role_name: 'Admin',
      auth_method: 'email_password',
      permissions_description: 'Can manage the product catalog and view all orders.',
    },
  ],
  entities: [
    {
      id: 'ent_prod0001',
      name: 'Product',
      attributes: [
        { name: 'title', type: 'string', required: true, unique: false },
        { name: 'price', type: 'decimal', required: true, unique: false },
        { name: 'stock', type: 'integer', required: true, unique: false },
      ],
      states: ['Active', 'OutOfStock'],
      owned_by_actor_id: null,
    },
    {
      id: 'ent_order001',
      name: 'Order',
      attributes: [
        { name: 'total', type: 'decimal', required: true, unique: false },
        { name: 'state', type: 'string', required: true, unique: false },
      ],
      states: ['Pending', 'Confirmed', 'Shipped'],
      owned_by_actor_id: 'act_cust0001',
    },
  ],
  relationships: [
    {
      id: 'rel_ord2prod',
      from_entity_id: 'ent_order001',
      to_entity_id: 'ent_prod0001',
      kind: 'one_to_many',
      name: 'order_items',
    },
  ],
  business_rules: [
    {
      id: 'rule_stock01',
      description: 'Product stock must be sufficient before an order can be confirmed.',
      trigger_condition: 'When Order transitions from Pending to Confirmed',
      enforcement_action: 'Reject with 422 if OrderItem.quantity exceeds Product.stock',
    },
  ],
  use_cases: [
    {
      id: 'uc_browse01',
      name: 'Browse Products',
      type: 'query',
      actor_id: 'act_cust0001',
      primary_entity_id: 'ent_prod0001',
      business_rule_ids: [],
      description: 'Customer views the product catalog.',
    },
    {
      id: 'uc_placeord',
      name: 'Place Order',
      type: 'command',
      actor_id: 'act_cust0001',
      primary_entity_id: 'ent_order001',
      business_rule_ids: ['rule_stock01'],
      description: 'Customer submits an order.',
    },
  ],
}

describe('Structured DDC builder — happy-path zod validation', () => {
  test('complete structured DDC passes CustomerConfigV2Schema', () => {
    const result = CustomerConfigV2Schema.safeParse(HAPPY_PATH_DDC)
    expect(result.success).toBe(true)
  })

  test('parsed DDC has correct number of actors', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    expect(ddc.actors).toHaveLength(2)
  })

  test('parsed DDC has correct number of entities', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    expect(ddc.entities).toHaveLength(2)
  })

  test('parsed DDC has one relationship', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    expect(ddc.relationships).toHaveLength(1)
  })

  test('parsed DDC has one business rule', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    expect(ddc.business_rules).toHaveLength(1)
  })

  test('parsed DDC has two use cases', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    expect(ddc.use_cases).toHaveLength(2)
  })

  test('use case actor_id references a valid actor', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    const actorIds = new Set(ddc.actors.map(a => a.id))
    for (const uc of ddc.use_cases) {
      expect(actorIds.has(uc.actor_id)).toBe(true)
    }
  })

  test('use case primary_entity_id references a valid entity', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    const entityIds = new Set(ddc.entities.map(e => e.id))
    for (const uc of ddc.use_cases) {
      expect(entityIds.has(uc.primary_entity_id)).toBe(true)
    }
  })

  test('business_rule_ids reference valid rules', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    const ruleIds = new Set(ddc.business_rules.map(r => r.id))
    for (const uc of ddc.use_cases) {
      for (const rid of uc.business_rule_ids) {
        expect(ruleIds.has(rid)).toBe(true)
      }
    }
  })

  test('entity with owned_by_actor_id references a valid actor', () => {
    const ddc = CustomerConfigV2Schema.parse(HAPPY_PATH_DDC)
    const actorIds = new Set(ddc.actors.map(a => a.id))
    for (const ent of ddc.entities) {
      if (ent.owned_by_actor_id) {
        expect(actorIds.has(ent.owned_by_actor_id)).toBe(true)
      }
    }
  })
})

describe('Structured DDC builder — empty optional collections', () => {
  test('DDC with no relationships still validates', () => {
    const result = CustomerConfigV2Schema.safeParse({ ...HAPPY_PATH_DDC, relationships: [] })
    expect(result.success).toBe(true)
  })

  test('DDC with no business rules still validates', () => {
    const result = CustomerConfigV2Schema.safeParse({ ...HAPPY_PATH_DDC, business_rules: [] })
    expect(result.success).toBe(true)
  })
})
