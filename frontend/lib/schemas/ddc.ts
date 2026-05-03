/**
 * Zod mirror of backend CustomerConfigV2 (app/schemas/customer_config_v2.py).
 *
 * Keep in sync with the Python schema. Same regex constraints, same min/max
 * lengths, same enum values.
 */

import { z } from 'zod'

// --- Enums ---

export const AuthMethod = z.enum(['anonymous', 'email_password', 'invite_only', 'sso'])
export const UseCaseType = z.enum(['command', 'query'])
export const DataFieldType = z.enum([
  'string', 'text', 'integer', 'decimal', 'boolean', 'datetime', 'date', 'uuid', 'json',
])
export const RelationshipKind = z.enum(['one_to_one', 'one_to_many', 'many_to_many'])
export const Industry = z.enum(['retail', 'healthcare', 'education', 'finance', 'services', 'other'])
export const VisualStyle = z.enum([
  'clean_minimal', 'bold_modern', 'warm_friendly', 'professional_corporate', 'playful',
])

// --- Atoms ---

export const AttributeSchema = z.object({
  name: z.string().regex(/^[a-z][a-z0-9_]*$/, 'snake_case attribute name required'),
  type: DataFieldType,
  required: z.boolean().default(true),
  unique: z.boolean().default(false),
  description: z.string().max(200).nullable().optional(),
})

export const RelationshipSchema = z.object({
  id: z.string(),
  from_entity_id: z.string(),
  to_entity_id: z.string(),
  kind: RelationshipKind,
  name: z.string().regex(/^[a-z][a-z0-9_]*$/, 'snake_case role name required'),
})

// --- Core Dimensions ---

export const ProjectContextSchema = z.object({
  name: z.string().min(2).max(60),
  domain_description: z.string().min(50).max(1500),
  industry: Industry,
  visual_style: VisualStyle.default('clean_minimal'),
  mobile_first: z.boolean().default(true),
})

export const ActorSchema = z.object({
  id: z.string(),
  role_name: z.string().regex(/^[A-Z][a-zA-Z0-9]*$/, 'PascalCase role name required'),
  auth_method: AuthMethod,
  permissions_description: z.string().min(10).max(500),
})

export const DomainEntitySchema = z.object({
  id: z.string(),
  name: z.string().regex(/^[A-Z][a-zA-Z0-9]*$/, 'PascalCase entity name required'),
  attributes: z.array(AttributeSchema).min(1),
  states: z.array(z.string()).min(1).default(['Active']),
  owned_by_actor_id: z.string().nullable().optional(),
})

export const BusinessRuleSchema = z.object({
  id: z.string(),
  description: z.string().min(10).max(500),
  trigger_condition: z.string().max(300),
  enforcement_action: z.string().max(300),
})

export const UseCaseSchema = z.object({
  id: z.string(),
  name: z.string().min(3).max(80),
  type: UseCaseType,
  actor_id: z.string(),
  primary_entity_id: z.string(),
  business_rule_ids: z.array(z.string()).default([]),
  description: z.string().max(400).nullable().optional(),
})

// --- Root Payload ---

export const DDC_SCHEMA_VERSION = 'ddc-v1' as const

export const CustomerConfigV2Schema = z.object({
  schema_version: z.literal('ddc-v1').default('ddc-v1'),
  context: ProjectContextSchema,
  actors: z.array(ActorSchema).min(1),
  entities: z.array(DomainEntitySchema).min(1),
  relationships: z.array(RelationshipSchema).default([]),
  business_rules: z.array(BusinessRuleSchema).default([]),
  use_cases: z.array(UseCaseSchema).min(1),
})

export type CustomerConfigV2 = z.infer<typeof CustomerConfigV2Schema>
export type ProjectContext = z.infer<typeof ProjectContextSchema>
export type Actor = z.infer<typeof ActorSchema>
export type DomainEntity = z.infer<typeof DomainEntitySchema>
export type Attribute = z.infer<typeof AttributeSchema>
export type Relationship = z.infer<typeof RelationshipSchema>
export type BusinessRule = z.infer<typeof BusinessRuleSchema>
export type UseCase = z.infer<typeof UseCaseSchema>
