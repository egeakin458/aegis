'use client'
import { WifiOff, RefreshCw } from 'lucide-react'
import type { ConnectionState } from '@/lib/types/ui'

interface Props {
  state: ConnectionState
  hasRun: boolean
  onReconnect?: () => void
}

export function ConnectionLostPill({ state, hasRun, onReconnect }: Props) {
  if (!hasRun || state === 'connected') return null

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2 rounded-full bg-slate-800 border border-slate-700 text-xs text-slate-300 shadow-lg">
      {state === 'reconnecting' ? (
        <>
          <RefreshCw size={13} className="animate-spin text-amber-400" />
          <span>Reconnecting...</span>
        </>
      ) : (
        <>
          <WifiOff size={13} className="text-red-400" />
          <span>Connection lost</span>
          {onReconnect && (
            <button
              type="button"
              onClick={onReconnect}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors"
            >
              <RefreshCw size={11} />
              Reconnect
            </button>
          )}
        </>
      )}
    </div>
  )
}
