"use client"

import { useEffect, useRef, useState } from "react"

import { staffRead } from "@/components/admin/staff-api"

import type { StatusSnapshot } from "./status-board-model"

const POLL_MS = 15_000
const LOAD_FAILED = "Status could not be loaded."

export const useStatusBoard = () => {
  const [snapshot, setSnapshot] = useState<StatusSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const pullRef = useRef<(refresh: boolean) => void>(() => {})

  useEffect(() => {
    let cancelled = false
    const pull = async (refresh: boolean) => {
      try {
        const response = await staffRead("/api/status")
        if (cancelled) {
          return
        }
        if (!response.ok) {
          setError(LOAD_FAILED)
          if (!refresh) {
            setSnapshot(null)
          }
          setLoading(false)
          return
        }
        const body = (await response.json()) as StatusSnapshot
        setSnapshot(body)
        setError(null)
        setLoading(false)
      } catch {
        if (cancelled) {
          return
        }
        setError(LOAD_FAILED)
        if (!refresh) {
          setSnapshot(null)
        }
        setLoading(false)
      }
    }
    pullRef.current = (refresh) => {
      void pull(refresh)
    }
    void pull(false)
    const timer = window.setInterval(() => {
      void pull(true)
    }, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  const handleRetry = () => {
    setLoading(true)
    setError(null)
    pullRef.current(false)
  }

  const handleRefresh = () => {
    pullRef.current(true)
  }

  return { snapshot, error, loading, handleRetry, handleRefresh }
}
