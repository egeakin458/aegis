'use client'
import { WifiOff, RefreshCw } from 'lucide-react'
import type { ConnectionState } from '@/lib/types/ui'

export function ConnectionLostPill({ state }: { state: ConnectionState }) {
  if (state === 'connected') return null

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2 rounded-full bg-slate-800 border border-slate-700 text-xs text-slate-300 shadow-lg">
      {state === 'reconnecting' ? (
        <>
          <RefreshCw size={13} className="animate-spin text-amber-400" />
          <span>Reconnecting...</span>
        </>
      ) : (
        <>
          <WifiOff size={13} className="text-red-400" />
          <span>Connection lost</span>
        </>
      )}
    </div>
  )
}
