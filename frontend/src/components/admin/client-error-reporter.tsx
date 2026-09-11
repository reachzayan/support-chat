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

export const installClientErrorReporting = () => {
  const onError = (event: ErrorEvent) => {
    void reportClientLog({
      level: "error",
      event: "ui_window_error",
      message: event.message || "Unhandled window error",
      detail: {
        path: window.location.pathname,
        error_class: event.error?.name ?? "Error",
        stack:
          typeof event.error?.stack === "string" ? event.error.stack.slice(0, 4000) : undefined,
        source: event.filename,
        line: event.lineno,
        column: event.colno,
      },
    })
  }

  const onRejection = (event: PromiseRejectionEvent) => {
    const reason = event.reason
    const message =
      reason instanceof Error
        ? reason.message
        : typeof reason === "string"
          ? reason
          : "Unhandled promise rejection"
    void reportClientLog({
      level: "error",
      event: "ui_unhandled_rejection",
      message: message.slice(0, 4000),
      detail: {
        path: window.location.pathname,
        error_class: reason instanceof Error ? reason.name : "UnhandledRejection",
        stack:
          reason instanceof Error && typeof reason.stack === "string"
            ? reason.stack.slice(0, 4000)
            : undefined,
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
