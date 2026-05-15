import { AgentOrbit } from '@/components/agent-orbit'
import { ConsolePane } from '@/components/console'
import type { OrbitPhase, ConsoleEntry } from '@/lib/types/ui'

const ALL_PHASES: OrbitPhase[] = [
  'idle', 'ra-running', 'ra-clarification', 'sa-running',
  'dev-running', 'qa-running', 'dev-revising', 'sa-revising',
  'complete', 'error',
]

const ALL_ENTRIES: ConsoleEntry[] = [
  { id: 'e1', type: 'agent-start', agent: 'ra', agentLabel: 'Requirements Analyst', timestamp: '10:00:00' },
  { id: 'e2', type: 'agent-complete', agent: 'ra', agentLabel: 'Requirements Analyst', tokensUsed: 3200, durationMs: 12000, timestamp: '10:00:12' },
  { id: 'e3', type: 'message', agent: 'sa', text: 'Designing the application architecture based on finalized requirements.', timestamp: '10:00:13' },
  { id: 'e4', type: 'progress-update', agent: 'dev', text: 'Generating database schema...', timestamp: '10:00:20' },
  { id: 'e5', type: 'file-generated', agent: 'dev', path: 'app/page.tsx', language: 'tsx', timestamp: '10:01:00' },
  { id: 'e6', type: 'file-generated', agent: 'dev', path: 'app/api/products/route.ts', language: 'ts', timestamp: '10:01:01' },
  {
    id: 'e7', type: 'clarification', agent: 'ra', submitted: false, timestamp: '10:00:08',
    questions: [
      { id: 'q1', question: 'What is the primary industry for this application?' },
      { id: 'q2', question: 'How many users do you expect concurrently?' },
    ],
  },
  {
    id: 'e8', type: 'config-finalized', agent: 'ra',
    projectSummary: 'A retail inventory management system for small businesses.',
    assumptions: ['Web-based, mobile-responsive', 'SQLite database', 'Up to 1000 products'],
    timestamp: '10:00:10',
  },
  {
    id: 'e9', type: 'revision-requested', agent: 'qa', verdict: 'revise_code',
    summary: 'Endpoints are wired and the schema is sound, but a few production-readiness gaps need a second pass before we ship.',
    codeQualityScore: 3,
    revisionNumber: 1, revisionMax: 2,
    issues: [
      {
        id: 'iss_1', severity: 'critical', category: 'security',
        affectedFile: 'app/api/notes/[id]/route.js',
        description: 'DELETE handler accepts any id without validating ownership — anonymous visitors can delete each other\'s notes.',
        suggestion: 'Add an ownership check or scope deletes to a session-bound visitor token before invoking the SQL DELETE.',
      },
      {
        id: 'iss_2', severity: 'major', category: 'reliability',
        affectedFile: 'app/api/notes/route.js',
        description: 'POST handler does not enforce the 500-character body limit from rule_body_max.',
        suggestion: 'Reject with HTTP 422 when body.length > 500 before inserting; mirror the error envelope used by other routes.',
      },
      {
        id: 'iss_3', severity: 'minor', category: 'ui',
        affectedFile: 'components/NoteCard.js',
        description: 'No loading state while a delete request is in flight; the row stays clickable and can produce duplicate requests.',
        suggestion: 'Disable the Delete button and show a spinner between request start and revalidation.',
      },
      {
        id: 'iss_4', severity: 'suggestion', category: 'quality',
        affectedFile: null,
        description: 'Consider extracting the shared "fetch + revalidate" pattern into a single hook to reduce duplication across pages.',
        suggestion: 'Pull the SWR boilerplate into hooks/useNotes.js and import from both list and detail pages.',
      },
    ],
    expanded: false, timestamp: '10:05:00',
  },
  {
    id: 'e9b', type: 'error-entry', agent: 'sa',
    message: "Our architect's draft didn't validate; retrying.",
    detail: undefined, terminal: false, timestamp: '10:05:30',
  },
  { id: 'e10', type: 'error-entry', agent: 'sys', message: 'Pipeline failed: LLM timeout', detail: 'Connection timed out after 30s', terminal: true, timestamp: '10:06:00' },
  { id: 'e11', type: 'summary', agent: 'sys', projectName: 'InventoryPro', totalTokens: 42000, durationMs: 380000, fileCount: 18, timestamp: '10:08:00' },
]

export default function DevEntriesPage() {
  return (
    <div className="min-h-screen bg-[#0f172a] p-8">
      <h1 className="text-white text-xl font-bold mb-2">Dev Harness — All States</h1>
      <p className="text-slate-500 text-sm mb-8">Every orbit phase and console entry variant.</p>

      {/* Orbit grid */}
      <h2 className="text-slate-300 text-sm font-semibold mb-4">Agent Orbit — All Phases</h2>
      <div className="grid grid-cols-5 gap-4 mb-12">
        {ALL_PHASES.map(phase => (
          <div key={phase} className="bg-slate-900 rounded-lg p-2">
            <p className="text-xs text-slate-500 text-center mb-1">{phase}</p>
            <AgentOrbit phase={phase} />
          </div>
        ))}
      </div>

      {/* Console entries */}
      <h2 className="text-slate-300 text-sm font-semibold mb-4">Console Entries — All Types</h2>
      <div className="max-w-2xl bg-slate-900 rounded-lg overflow-hidden">
        <ConsolePane entries={ALL_ENTRIES} />
      </div>
    </div>
  )
}
