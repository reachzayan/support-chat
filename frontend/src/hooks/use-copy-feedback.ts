"use client"

import { useCallback, useEffect, useRef, useState } from "react"

const COPY_FEEDBACK_MS = 1000

export const useCopyFeedback = () => {
  const [copied, setCopied] = useState(false)
  const timeoutRef = useRef<number | null>(null)

  const copy = useCallback(async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current)
      }
      setCopied(true)
      timeoutRef.current = window.setTimeout(() => {
        timeoutRef.current = null
        setCopied(false)
      }, COPY_FEEDBACK_MS)
      return true
    } catch {
      return false
    }
  }, [])

  useEffect(
    () => () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current)
      }
    },
    [],
  )

  return { copied, copy }
}
