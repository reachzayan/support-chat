"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-array-as-prop -- Card fields and actions are built per record. */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"

import { LogTableSkeleton } from "@/components/admin/loading-skeleton"
import { staffRead } from "@/components/admin/staff-api"
import { StaffHeader } from "@/components/admin/staff-nav"
import { useSearchTarget } from "@/components/search/workspace-route"
import { Button } from "@/components/ui/button"
import { RecordCard, RecordCardList } from "@/components/ui/record-cards"
import { Spinner } from "@/components/ui/spinner"
import { useIsMobile } from "@/hooks/use-mobile"

export type AppLogRow = {
  id: string
  created_at: string
  level: string
  source: string
  logger_name: string
  event: string
  message: string
  detail: Record<string, unknown> | null
}

type LogsConsoleProps = {
  isAdmin: boolean
  displayName: string
}

const formatDetail = (detail: Record<string, unknown> | null) => {
  if (!detail || Object.keys(detail).length === 0) {
    return "—"
  }
  try {
    return JSON.stringify(detail)
  } catch {
    return "—"
  }
}

const downloadDump = async () => {
  const response = await staffRead("/api/logs/dump")
  if (!response.ok) {
    throw new Error("dump_failed")
  }
  const text = await response.text()
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `supportchat-logs-${new Date().toISOString().slice(0, 10)}.txt`
  anchor.click()
  URL.revokeObjectURL(url)
}

const DumpButton = ({ dumping, onDump }: { dumping: boolean; onDump: () => void }) => (
  <Button
    type="button"
    variant="default"
    size="lg"
    onClick={onDump}
    disabled={dumping}
    aria-label="Dump last 7 days"
    className="font-bold"
  >
    {dumping ? <Spinner data-icon="inline-start" /> : null}
    {dumping ? "Dumping…" : "Dump last 7 days"}
  </Button>
)

const levelClass = (level: string) => {
  const value = level.toLowerCase()
  if (value === "error" || value === "critical") {
    return "bg-ember/10 text-ember"
  }
  if (value === "warning" || value === "warn") {
    return "bg-steel/10 text-steel"
  }
  return "bg-ice-2 text-mute"
}

const LogsCards = ({ items }: { items: AppLogRow[] }) => (
  <div className="border-line bg-paper overflow-hidden rounded-[8px] border">
    <RecordCardList label="Application logs">
      {items.map((row) => {
        const detail = formatDetail(row.detail)
        return (
          <RecordCard
            key={row.id}
            eyebrow={<span className="font-mono">{row.created_at}</span>}
            title={row.event}
            badge={
              <span
                className={`rounded-[6px] px-1.5 py-0.5 text-[10px] font-bold uppercase ${levelClass(row.level)}`}
              >
                {row.level}
              </span>
            }
            fields={[
              { label: "Source", value: row.source },
              { label: "Message", value: row.message, wide: true },
              ...(detail === "—"
                ? []
                : [
                    {
                      label: "Detail",
                      value: (
                        <span className="line-clamp-4" title={detail}>
                          {detail}
                        </span>
                      ),
                      mono: true,
                      wide: true,
                    },
                  ]),
            ]}
          />
        )
      })}
    </RecordCardList>
  </div>
)

const LogsTable = ({ items }: { items: AppLogRow[] }) => (
  <div className="border-line bg-paper overflow-x-scroll rounded-[8px] border">
    <table className="w-full min-w-[960px] text-left text-sm" aria-label="Application logs">
      <thead className="bg-ice-2 border-line border-b">
        <tr>
          {(["Timestamp", "Level", "Source", "Event", "Message", "Detail"] as const).map(
            (label) => (
              <th
                key={label}
                className="text-mute px-3 py-2.5 text-[10px] font-semibold tracking-[0.12em] uppercase"
              >
                {label}
              </th>
            ),
          )}
        </tr>
      </thead>
      <tbody>
        {items.map((row) => {
          const detail = formatDetail(row.detail)
          return (
            <tr key={row.id} className="border-line border-b last:border-b-0">
              <td className="text-ink px-3 py-2.5 font-mono text-xs whitespace-nowrap">
                {row.created_at}
              </td>
              <td className="text-ink px-3 py-2.5 font-semibold uppercase">{row.level}</td>
              <td className="text-ink px-3 py-2.5">{row.source}</td>
              <td className="text-ink px-3 py-2.5 font-semibold">{row.event}</td>
              <td className="text-ink px-3 py-2.5">{row.message}</td>
              <td
                className="text-mute max-w-[28rem] truncate px-3 py-2.5 font-mono text-xs"
                title={detail}
              >
                {detail}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  </div>
)

const LogsBody = ({
  error,
  loading,
  items,
}: {
  error: string | null
  loading: boolean
  items: AppLogRow[]
}) => {
  const isMobile = useIsMobile()
  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5 sm:py-5 lg:px-8">
      {error ? <p className="text-ember mb-3 text-sm font-semibold">{error}</p> : null}
      {loading ? <LogTableSkeleton /> : null}
      {!loading && items.length === 0 && !error ? (
        <p className="text-mute text-sm">No application logs in the last 7 days.</p>
      ) : null}
      {items.length > 0 ? (
        isMobile ? (
          <LogsCards items={items} />
        ) : (
          <LogsTable items={items} />
        )
      ) : null}
    </div>
  )
}

export const LogsConsole = ({ isAdmin, displayName }: LogsConsoleProps) => {
  const target = useSearchTarget()
  const [items, setItems] = useState<AppLogRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [dumping, setDumping] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      const response = await staffRead(
        target.log ? `/api/logs/${encodeURIComponent(target.log)}` : "/api/logs",
      ).catch(() => null)
      if (cancelled) {
        return
      }
      if (!response?.ok) {
        setError(
          response?.status === 403
            ? "Only admins can view application logs."
            : "Could not load application logs.",
        )
        setItems([])
        setLoading(false)
        return
      }
      const body = (await response.json()) as { items: AppLogRow[] } | AppLogRow
      setItems("items" in body ? body.items : [body])
      setLoading(false)
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [target.log])

  const handleDump = useCallback(() => {
    setDumping(true)
    setError(null)
    void downloadDump()
      .catch(() => {
        setError("Could not dump logs for the last 7 days.")
      })
      .finally(() => {
        setDumping(false)
      })
  }, [])

  const action = useMemo<ReactNode>(
    () => (isAdmin ? <DumpButton dumping={dumping} onDump={handleDump} /> : null),
    [isAdmin, dumping, handleDump],
  )

  return (
    <div className="view-transition-enter bg-ice flex min-h-0 flex-1 flex-col">
      <StaffHeader
        title="Application logs"
        description={`Elaborative failure traces for the last 7 days. Signed in as ${displayName}. Transcript bodies and credentials are never stored.`}
        action={action}
      />
      <LogsBody error={error} loading={loading} items={items} />
    </div>
  )
}
