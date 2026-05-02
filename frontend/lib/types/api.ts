// Re-exports from generated OpenAPI schema + hand-written SSE event types
// (event types are not in OpenAPI because SSE sends raw JSON)
import type { components } from '@/lib/utils/generated/schema'

// CustomerConfig and sub-types (authoritative: generated from backend OpenAPI)
export type CustomerConfig = components['schemas']['CustomerConfig']
export type BusinessContext = components['schemas']['BusinessContext']
export type ProblemStatement = components['schemas']['ProblemStatement']
export type Features = components['schemas']['Features']
export type FeatureRequest = components['schemas']['FeatureRequest']
export type DataRequirements = components['schemas']['DataRequirements']
export type DesignPreferences = components['schemas']['DesignPreferences']
export type TechnicalRequirements = components['schemas']['TechnicalRequirements']
export type ProjectMeta = components['schemas']['ProjectMeta']
export type FileUpload = components['schemas']['FileUpload']

// Enum types
export type IndustryType = components['schemas']['IndustryType']
export type BusinessSize = components['schemas']['BusinessSize']
export type UserType = components['schemas']['UserType']
export type AccessScope = components['schemas']['AccessScope']
export type DesignStyle = components['schemas']['DesignStyle']
export type MobileSupport = components['schemas']['MobileSupport']
export type DataVolume = components['schemas']['DataVolume']

// API response types (not in OpenAPI schema)
export interface StartRunResponse { run_id: string; status: string }
export interface OutputFile { path: string; language: string; description?: string; content?: string }
export interface FeatureImplementation { feature_id: string; description: string; implementation_notes?: string | null }
export interface OutputManifest { run_id: string; files: OutputFile[]; features_implemented?: FeatureImplementation[] }

// Pipeline event types (hand-written — SSE sends raw JSON not covered by OpenAPI)
export type AgentName =
  | 'requirements_analyst'
  | 'solution_architect'
  | 'developer'
  | 'qa_reviewer'
  | 'system'

export type EventType =
  | 'pipeline_started' | 'pipeline_complete' | 'pipeline_partial' | 'pipeline_failed'
  | 'agent_start' | 'agent_complete'
  | 'llm_call_start' | 'llm_call_complete'
  | 'clarification_needed' | 'clarification_received' | 'config_finalized'
  | 'revision_requested' | 'revision_started'
  | 'validation_passed' | 'validation_failed'
  | 'file_generated' | 'progress_update'
  | 'error'

export type PipelineStateValue =
  | 'intake' | 'requirements' | 'clarification' | 'design' | 'development'
  | 'review' | 'code_revision' | 'design_revision' | 'complete' | 'failed'

export interface TokenUsage { input_tokens: number; output_tokens: number }

export interface PipelineEvent {
  event_id: string
  run_id: string
  timestamp: string
  agent: AgentName
  event_type: EventType
  message: string
  data: Record<string, unknown>
  tokens_used?: TokenUsage | null
  duration_ms?: number | null
  pipeline_state?: PipelineStateValue | null
}
