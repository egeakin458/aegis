export type AgentId = 'ra' | 'sa' | 'dev' | 'qa'

export type OrbitPhase =
  | 'idle'
  | 'ra-running'
  | 'ra-clarification'
  | 'sa-running'
  | 'dev-running'
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
  | 'revision-requested'
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
export interface FileGeneratedEntry extends BaseEntry { type: 'file-generated'; path: string; language: string }
export interface ClarificationQuestion { id: string; question: string; answer?: string }
export interface ClarificationEntry extends BaseEntry { type: 'clarification'; questions: ClarificationQuestion[]; submitted: boolean }
export interface ConfigFinalizedEntry extends BaseEntry { type: 'config-finalized'; projectSummary: string; assumptions: string[] }
export interface RevisionRequestedEntry extends BaseEntry { type: 'revision-requested'; verdict: string; issues: string[]; revisionNumber: number; expanded: boolean }
export interface ErrorEntry extends BaseEntry { type: 'error-entry'; message: string; detail?: string; terminal: boolean }
export interface SummaryEntry extends BaseEntry { type: 'summary'; projectName: string; totalTokens: number; durationMs: number; fileCount: number }

export type ConsoleEntry =
  | AgentStartEntry | AgentCompleteEntry | MessageEntry | ProgressUpdateEntry
  | FileGeneratedEntry | ClarificationEntry | ConfigFinalizedEntry
  | RevisionRequestedEntry | ErrorEntry | SummaryEntry

export interface PipelineState {
  phase: OrbitPhase
  activeAgent: AgentId | null
  entries: ConsoleEntry[]
  totalTokens: number
  startTime: string | null
  connectionState: ConnectionState
  isReplay: boolean
}
