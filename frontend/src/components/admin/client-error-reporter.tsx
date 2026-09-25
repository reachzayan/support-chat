"use client"

import { useEffect } from "react"

import { getAccessToken, staffRequest } from "@/lib/auth-client"

const reportClientLog = async (payload: {
  level: string
  event: string
  message: string
  detail: Record<string, unknown>
}) => {
  if (!getAccessToken()) {
    return
  }
  try {
    await staffRequest("/api/logs/client", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  } catch {
    // Client reporting must never break the admin UI.
  }
}

export const safeClientErrorMessage = (value: unknown, fallback: string): string =>
  value instanceof Error && value.name ? value.name.slice(0, 128) : fallback

export const installClientErrorReporting = () => {
  const onError = (event: ErrorEvent) => {
    void reportClientLog({
      level: "error",
      event: "ui_window_error",
      message: safeClientErrorMessage(event.error, "Unhandled window error"),
      detail: {
        path: window.location.pathname,
        error_class: event.error?.name ?? "Error",
        source: event.filename,
        line: event.lineno,
        column: event.colno,
      },
    })
  }

  const onRejection = (event: PromiseRejectionEvent) => {
    const reason = event.reason
    void reportClientLog({
      level: "error",
      event: "ui_unhandled_rejection",
      message: safeClientErrorMessage(reason, "Unhandled promise rejection"),
      detail: {
        path: window.location.pathname,
        error_class: reason instanceof Error ? reason.name : "UnhandledRejection",
      },
    })
  }

  window.addEventListener("error", onError)
  window.addEventListener("unhandledrejection", onRejection)
  return () => {
    window.removeEventListener("error", onError)
    window.removeEventListener("unhandledrejection", onRejection)
  }
}

export const ClientErrorReporter = () => {
  useEffect(() => installClientErrorReporting(), [])
  return null
}
