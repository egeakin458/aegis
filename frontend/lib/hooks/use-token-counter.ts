'use client'
import { useState, useEffect, useRef } from 'react'

export function useTokenCounter(target: number, duration = 600): number {
  const [displayed, setDisplayed] = useState(target)
  const prevRef = useRef(target)

  useEffect(() => {
    const start = prevRef.current
    if (start === target) return
    const diff = target - start
    const startTime = performance.now()

    const tick = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      setDisplayed(Math.round(start + diff * progress))
      if (progress < 1) {
        requestAnimationFrame(tick)
      } else {
        prevRef.current = target
      }
    }

    requestAnimationFrame(tick)
  }, [target, duration])

  return displayed
}
