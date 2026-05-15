export type AgentId = 'ra' | 'sa' | 'dev' | 'qa'

export type OrbitPhase =
  | 'idle'
  | 'ra-running'
  | 'ra-clarification'
  | 'sa-running'
  | 'dev-running'
  | 'build-check-running'
  | 'build-check-failed'
  | 'qa-running'
  | 'dev-revising'
  | 'sa-revising'
  | 'complete'
  | 'error'

export type ConnectionState = 'connected' | 'reconnecting' | 'disconnected'

export type ConsoleEntryType =
  | 'agent-start'
  | 'agent-complete'
  | 'message'
  | 'progress-update'
  | 'file-generated'
  | 'clarification'
  | 'config-finalized'
  | 'config-submitted'
  | 'flow-primer'
  | 'revision-requested'
  | 'build-check'
  | 'error-entry'
  | 'summary'

export interface BaseEntry {
  id: string
  type: ConsoleEntryType
  agent: AgentId | 'sys'
  timestamp: string
}

export interface AgentStartEntry extends BaseEntry { type: 'agent-start'; agentLabel: string }
export interface AgentCompleteEntry extends BaseEntry { type: 'agent-complete'; agentLabel: string; tokensUsed: number; durationMs: number }
export interface MessageEntry extends BaseEntry { type: 'message'; text: string }
export interface ProgressUpdateEntry extends BaseEntry { type: 'progress-update'; text: string }
export interface FileGeneratedEntry extends BaseEntry { type: 'file-generated'; path: string; language: string; action?: 'created' | 'updated' | 'removed' }
export interface ClarificationQuestion { id: string; question: string; answer?: string }
export interface ClarificationEntry extends BaseEntry { type: 'clarification'; questions: ClarificationQuestion[]; submitted: boolean }
export interface ConfigFinalizedEntry extends BaseEntry { type: 'config-finalized'; projectSummary: string; assumptions: string[] }
export interface ConfigSubmittedEntry extends BaseEntry { type: 'config-submitted'; projectName: string; description: string }
export interface FlowPrimerEntry extends BaseEntry { type: 'flow-primer' }
export type IssueSeverity = 'critical' | 'major' | 'minor' | 'suggestion'
export interface ReviewIssue {
  id: string
  severity: IssueSeverity
  category: string
  affectedFile: string | null
  description: string
  suggestion: string | null
}
export interface RevisionRequestedEntry extends BaseEntry {
  type: 'revision-requested'
  verdict: 'revise_code' | 'revise_design'
  summary: string
  issues: ReviewIssue[]
  codeQualityScore: number
  revisionNumber: number
  revisionMax: number
  expanded: boolean
}
export interface ErrorEntry extends BaseEntry { type: 'error-entry'; message: string; detail?: string; terminal: boolean }
export interface FeatureStatus { name: string; implemented: boolean; evidence?: string | null }
export interface SummaryEntry extends BaseEntry { type: 'summary'; projectName: string; totalTokens: number; durationMs: number; fileCount: number; partial?: boolean; featureStatus?: FeatureStatus[] }

export interface BuildCheckIssue { file: string; line?: number | null; column?: number | null; severity: 'error' | 'warning'; message: string; check: string }
export interface BuildCheckEntry extends BaseEntry { type: 'build-check'; passed: boolean; filesChecked: number; durationMs: number; issues: BuildCheckIssue[] }

export type ConsoleEntry =
  | AgentStartEntry | AgentCompleteEntry | MessageEntry | ProgressUpdateEntry
  | FileGeneratedEntry | ClarificationEntry | ConfigFinalizedEntry
  | ConfigSubmittedEntry | FlowPrimerEntry
  | RevisionRequestedEntry | BuildCheckEntry | ErrorEntry | SummaryEntry

export interface PipelineState {
  phase: OrbitPhase
  activeAgent: AgentId | null
  entries: ConsoleEntry[]
  totalTokens: number
  startTime: string | null
  connectionState: ConnectionState
  isReplay: boolean
}
