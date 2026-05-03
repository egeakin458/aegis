/**
 * Maps free-text DDC intake form values to a minimal CustomerConfigV2 payload.
 *
 * The Requirements Analyst expands this skeleton into a full DDC by inferring
 * actors, entities, business rules, and use cases from the domain description.
 */

import type { FreeTextFormValues } from '@/lib/schemas/intake-form'
import type { CustomerConfigV2 } from '@/lib/schemas/ddc'

export function mapFreeTextToDDC(values: FreeTextFormValues): CustomerConfigV2 {
  const projectName = values.projectName
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')

  return {
    schema_version: 'ddc-v1',
    context: {
      name: projectName,
      domain_description: values.domainDescription,
      industry: values.industry,
      visual_style: values.visualStyle,
      mobile_first: values.mobileFirst,
    },
    actors: [
      {
        id: 'act_placeholder',
        role_name: 'Customer',
        auth_method: 'anonymous',
        permissions_description: 'Placeholder actor. RA will refine based on domain description.',
      },
    ],
    entities: [
      {
        id: 'ent_placeholder',
        name: 'Item',
        attributes: [
          { name: 'name', type: 'string', required: true, unique: false },
        ],
        states: ['Active'],
        owned_by_actor_id: null,
      },
    ],
    relationships: [],
    business_rules: [],
    use_cases: [
      {
        id: 'uc_placeholder',
        name: 'Use Application',
        type: 'query',
        actor_id: 'act_placeholder',
        primary_entity_id: 'ent_placeholder',
        business_rule_ids: [],
        description: 'Placeholder use case. RA will derive real use cases from domain description.',
      },
    ],
  }
}
