// Hand-written types matching backend Pydantic schemas.
// Regenerate with: npm run gen:types (requires backend running on port 8000)

export type IndustryType = 'retail' | 'food_and_beverage' | 'professional_services' | 'healthcare' | 'education' | 'manufacturing' | 'other'
export type BusinessSize = '1-5' | '6-20' | '21-50' | '50+'
export type UserType = 'owner' | 'employees' | 'customers' | 'all'
export type AccessScope = 'just_me' | 'team_network' | 'anyone_internet'
export type DesignStyle = 'clean_minimal' | 'professional_corporate' | 'modern_colorful' | 'no_preference'
export type MobileSupport = 'yes' | 'no' | 'nice_to_have'
export type DataVolume = 'under_100' | '100-1000' | '1000-10000' | '10000+'

export interface FeatureRequest { description: string; priority: number }
export interface FileUpload { filename: string; category: string; file_path?: string | null }
export interface BusinessContext { name: string; industry: IndustryType; industry_other?: string | null; description: string; size: BusinessSize }
export interface ProblemStatement { problem: string; users: UserType[]; current_process?: string | null }
export interface Features { requested: FeatureRequest[] }
export interface DataRequirements { entities: string; has_existing_data: boolean; uploads: FileUpload[]; volume: DataVolume }
export interface DesignPreferences { colors?: string[] | null; logo?: FileUpload | null; references: FileUpload[]; style: DesignStyle }
export interface TechnicalRequirements { access_scope: AccessScope; auth_required: boolean; user_roles?: string | null; mobile: MobileSupport }
export interface ProjectMeta { deadline?: string | null; notes?: string | null; submitted_at: string }

export interface CustomerConfig {
  business_context: BusinessContext
  problem_statement: ProblemStatement
  features: Features
  data: DataRequirements
  design: DesignPreferences
  technical: TechnicalRequirements
  meta: ProjectMeta
}

export type AgentName =
  | 'requirements_analyst'
  | 'solution_architect'
  | 'developer'
  | 'qa_reviewer'
  | 'system'

export type EventType =
  | 'pipeline_started'
  | 'pipeline_complete'
  | 'pipeline_failed'
  | 'agent_start'
  | 'agent_complete'
  | 'llm_call_start'
  | 'llm_call_complete'
  | 'clarification_needed'
  | 'clarification_received'
  | 'config_finalized'
  | 'revision_requested'
  | 'revision_started'
  | 'validation_passed'
  | 'validation_failed'
  | 'file_generated'
  | 'progress_update'
  | 'error'

export type PipelineStateValue =
  | 'intake'
  | 'requirements'
  | 'clarification'
  | 'design'
  | 'development'
  | 'review'
  | 'code_revision'
  | 'design_revision'
  | 'complete'
  | 'failed'

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

export interface StartRunResponse { run_id: string; status: string }

export interface OutputFile {
  path: string
  language: string
  description?: string
  content?: string
}

export interface OutputManifest {
  run_id: string
  files: OutputFile[]
}
