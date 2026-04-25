'use client'
import { useState, useEffect } from 'react'

export function useElapsed(startTime: string | null, frozen: boolean): number {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!startTime) { setElapsed(0); return }
    const start = new Date(startTime).getTime()
    if (frozen) { setElapsed(Date.now() - start); return }
    const update = () => setElapsed(Date.now() - start)
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [startTime, frozen])

  return elapsed
}
