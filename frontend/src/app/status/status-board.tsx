"use client"

import { cn } from "cn"
import { AlertCircle, CheckCircle2 } from "lucide-react"
import Link from "next/link"

import { StaffPageSkeleton } from "@/components/admin/loading-skeleton"
import { RetryError } from "@/components/admin/retry-error"
import { StaffHeader } from "@/components/admin/staff-nav"
import { Button } from "@/components/ui/button"

import {
  assistantLabel,
  availabilityLabel,
  failuresHeading,
  formatCheckedAt,
  formatUptime,
  knowledgeLabel,
  latencyLabel,
  latencySparkPath,
  SPARK_HEIGHT,
  SPARK_WIDTH,
  serviceTone,
  specialistLine,
  unansweredLine,
  visitorLine,
  waitingLabel,
  widgetLabel,
  type AvailabilityTone,
  type OverallState,
  type ServiceState,
  type StatusIncident,
  type StatusMonitor,
  type StatusSite,
  type StatusSnapshot,
} from "./status-board-model"
import { useStatusBoard } from "./use-status-board"

const LOAD = [
  { key: "waiting", label: "Waiting", field: "waiting" },
  { key: "bot", label: "With the assistant", field: "bot" },
  { key: "live", label: "With a specialist", field: "live" },
  { key: "closed", label: "Closed today", field: "closed_today" },
] as const

const PERIODS = [
  { key: "hours_24", label: "Last 24 hours" },
  { key: "days_7", label: "Last 7 days" },
  { key: "days_30", label: "Last 30 days" },
  { key: "days_90", label: "Last 90 days" },
] as const

const TAPE_SLOTS = Array.from({ length: 30 }, (_, offset) => `d${offset + 1}`)

const lampClass = (state: ServiceState) => {
  if (state === "ok") {
    return "bg-steel"
  }
  return "bg-ember"
}

const bannerClass = (overall: OverallState) => {
  if (overall === "ok") {
    return "border-steel/25 bg-steel/10 text-navy"
  }
  return "border-ember/25 bg-ember/10 text-navy"
}

const bannerIconClass = (overall: OverallState) => {
  if (overall === "ok") {
    return "text-steel"
  }
  return "text-ember"
}

const knowledgeClass = (tone: StatusSite["knowledge"]) => {
  if (tone === "failed") {
    return "text-ember font-semibold"
  }
  return "text-ink"
}

const tapeClass = (tone: AvailabilityTone) => {
  if (tone === "up") {
    return "bg-steel"
  }
  if (tone === "degraded") {
    return "bg-ember"
  }
  return "bg-line"
}

const AvailabilityTape = ({ days }: { days: AvailabilityTone[] }) => (
  <figure aria-label={availabilityLabel(days)} className="m-0 flex h-8 items-end gap-px">
    {TAPE_SLOTS.map((slot, offset) => (
      <span
        key={slot}
        aria-hidden="true"
        className={cn("h-full w-1.5 rounded-[1px]", tapeClass(days[offset] ?? "empty"))}
      />
    ))}
  </figure>
)

const LatencySpark = ({ hours }: { hours: (number | null)[] }) => {
  const spark = latencySparkPath(hours)
  return (
    <figure aria-label={latencyLabel(hours)} className="m-0">
      <svg
        viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`}
        className="h-9 w-44 overflow-visible"
        aria-hidden="true"
      >
        <line x1="0" y1="31" x2={SPARK_WIDTH} y2="31" stroke="#E5EAF2" strokeWidth="1" />
        {spark ? (
          <>
            <path d={spark.area} fill="#2456A0" fillOpacity="0.16" />
            <path
              d={spark.line}
              fill="none"
              stroke="#2456A0"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        ) : null}
      </svg>
    </figure>
  )
}

const OverallBanner = ({ snapshot }: { snapshot: StatusSnapshot }) => {
  const Icon = snapshot.overall === "ok" ? CheckCircle2 : AlertCircle
  return (
    <output
      className={cn(
        "flex shrink-0 items-center gap-3 rounded-lg border px-4 py-3",
        bannerClass(snapshot.overall),
      )}
    >
      <Icon
        aria-hidden="true"
        className={cn("size-5 shrink-0", bannerIconClass(snapshot.overall))}
      />
      <h2 className="heading text-base">{snapshot.headline}</h2>
    </output>
  )
}

const UptimeCards = ({ snapshot }: { snapshot: StatusSnapshot }) => (
  <section className="border-line bg-paper shrink-0 overflow-hidden rounded-lg border">
    <div className="bg-line grid grid-cols-2 gap-px lg:grid-cols-4">
      {PERIODS.map((period) => (
        <article
          key={period.key}
          aria-labelledby={`status-uptime-${period.key}`}
          className="bg-paper px-5 py-4"
        >
          <p className="text-navy font-mono text-3xl font-semibold tracking-tight">
            {formatUptime(snapshot.uptime[period.key])}
          </p>
          <h3 id={`status-uptime-${period.key}`} className="text-mute mt-1 text-xs font-medium">
            {period.label}
          </h3>
        </article>
      ))}
    </div>
  </section>
)

const ServiceRow = ({ monitor }: { monitor: StatusMonitor }) => (
  <tr className="border-line border-b last:border-b-0">
    <td className="px-5 py-3">
      <span
        aria-hidden="true"
        className={cn("mt-1 block size-2.5 rounded-full", lampClass(monitor.state))}
      />
      <span className="sr-only">{serviceTone(monitor.state)}</span>
    </td>
    <th scope="row" className="text-navy px-5 py-3 text-left font-semibold">
      {monitor.name}
    </th>
    <td className="px-5 py-3">
      <AvailabilityTape days={monitor.availability_30d} />
    </td>
    <td className="px-5 py-3">
      <LatencySpark hours={monitor.latency_24h} />
    </td>
  </tr>
)

const ServiceTable = ({
  snapshot,
  onRefresh,
}: {
  snapshot: StatusSnapshot
  onRefresh: () => void
}) => (
  <section className="border-line bg-paper shrink-0 overflow-hidden rounded-lg border">
    <div className="overflow-x-scroll">
      <table className="w-full min-w-[40rem] text-left text-sm" aria-label="Services">
        <thead className="bg-ice-2 border-line border-b">
          <tr>
            {(
              ["Status", "Name", "Availability — last 30d", "Median response — last 24h"] as const
            ).map((label) => (
              <th
                key={label}
                className="text-mute px-5 py-2.5 text-[10px] font-semibold tracking-[0.12em] uppercase"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {snapshot.monitors.map((monitor) => (
            <ServiceRow key={monitor.key} monitor={monitor} />
          ))}
        </tbody>
      </table>
    </div>
    <div className="border-line flex flex-wrap items-center justify-between gap-3 border-t px-5 py-3">
      <p className="text-mute flex flex-wrap gap-x-3 gap-y-1 text-xs">
        <span>Last updated {formatCheckedAt(snapshot.checked_at)}</span>
        <span aria-hidden="true">·</span>
        <span>Next update in 15 seconds</span>
      </p>
      <Button type="button" variant="outline" size="lg" onClick={onRefresh}>
        Refresh
      </Button>
    </div>
  </section>
)

const IncidentList = ({ incidents }: { incidents: StatusIncident[] }) => (
  <section className="border-line bg-paper shrink-0 rounded-lg border">
    <h2 className="text-navy heading border-line border-b px-5 py-3 text-sm">Incidents</h2>
    <ol aria-label="Incidents" className="divide-line divide-y">
      {incidents.map((item) => (
        <li key={item.date} className="flex items-baseline justify-between gap-4 px-5 py-3">
          <time className="text-navy font-mono text-xs font-semibold" dateTime={item.date}>
            {item.date}
          </time>
          <p className="text-mute text-sm">{item.summary}</p>
        </li>
      ))}
    </ol>
  </section>
)

const LoadTape = ({ snapshot }: { snapshot: StatusSnapshot }) => (
  <section className="border-line bg-paper shrink-0 overflow-hidden rounded-lg border">
    <div className="bg-line grid grid-cols-2 gap-px lg:grid-cols-4">
      {LOAD.map((item) => (
        <article
          key={item.key}
          aria-labelledby={`status-load-${item.key}`}
          className="bg-paper px-5 py-4"
        >
          <p className="text-navy font-mono text-3xl font-semibold tracking-tight">
            {snapshot.inbox[item.field]}
          </p>
          <h3 id={`status-load-${item.key}`} className="text-mute mt-1 text-xs font-medium">
            {item.label}
          </h3>
        </article>
      ))}
    </div>
    <p className="border-line text-mute flex flex-wrap gap-x-3 gap-y-1 border-t px-5 py-3 text-xs">
      <span>{visitorLine(snapshot.live.visitors)}</span>
      <span aria-hidden="true">·</span>
      <span>{specialistLine(snapshot.live.specialists)}</span>
      <span aria-hidden="true">·</span>
      <Link
        href="/admin/suggested-faqs"
        className="text-steel hover:text-navy font-semibold no-underline"
      >
        {unansweredLine(snapshot.gaps_open)}
      </Link>
    </p>
  </section>
)

const WebsiteTable = ({ sites }: { sites: StatusSite[] }) => (
  <section className="border-line bg-paper shrink-0 overflow-hidden rounded-lg border">
    <div className="border-line flex items-baseline justify-between gap-3 border-b px-5 py-3">
      <h2 className="text-navy heading text-sm">Websites</h2>
      <Link
        href="/admin/sites"
        className="text-steel hover:text-navy text-xs font-semibold no-underline"
      >
        Manage sites
      </Link>
    </div>
    <div className="overflow-x-scroll">
      <table className="w-full min-w-[36rem] text-left text-sm" aria-label="Websites">
        <thead className="bg-ice-2 border-line border-b">
          <tr>
            {(["Website", "Widget", "Assistant", "Knowledge", "Waiting"] as const).map((label) => (
              <th
                key={label}
                className="text-mute px-5 py-2.5 text-[10px] font-semibold tracking-[0.12em] uppercase"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sites.map((site) => (
            <tr key={site.id} className="border-line border-b last:border-b-0">
              <th scope="row" className="text-navy px-5 py-3 font-semibold">
                {site.name}
              </th>
              <td className="text-ink px-5 py-3">{widgetLabel(site.widget_installed)}</td>
              <td className="text-ink px-5 py-3">{assistantLabel(site.bot_enabled)}</td>
              <td className={cn("px-5 py-3", knowledgeClass(site.knowledge))}>
                {knowledgeLabel(site.knowledge)}
              </td>
              <td className="text-ink px-5 py-3">{waitingLabel(site.waiting)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </section>
)

const FailureList = ({ snapshot }: { snapshot: StatusSnapshot }) => (
  <section className="border-line bg-paper shrink-0 rounded-lg border">
    <div className="border-line flex items-baseline justify-between gap-3 border-b px-5 py-3">
      <h2 className="text-navy heading text-sm">{failuresHeading(snapshot.errors_24h)}</h2>
      <Link
        href="/admin/logs"
        className="text-steel hover:text-navy text-xs font-semibold no-underline"
      >
        Application logs
      </Link>
    </div>
    {snapshot.recent_errors.length === 0 ? (
      <p className="text-mute px-5 py-4 text-sm">The last day of traces is clean.</p>
    ) : (
      <ul>
        {snapshot.recent_errors.map((row) => (
          <li
            key={row.id}
            className="border-line flex flex-col gap-1 border-b px-5 py-3 last:border-b-0 sm:flex-row sm:items-baseline sm:justify-between"
          >
            <div className="min-w-0">
              <p className="text-navy text-sm font-semibold">{row.event}</p>
              <p className="text-mute mt-0.5 truncate text-xs">{row.message}</p>
            </div>
            <p className="text-mute shrink-0 font-mono text-[11px]">
              {new Date(row.created_at).toLocaleString()}
            </p>
          </li>
        ))}
      </ul>
    )}
  </section>
)

const StatusBody = ({
  snapshot,
  onRefresh,
}: {
  snapshot: StatusSnapshot
  onRefresh: () => void
}) => (
  <div id="main-content" className="mx-auto w-full max-w-5xl space-y-5 px-5 py-6 lg:px-8 lg:py-8">
    <OverallBanner snapshot={snapshot} />
    <UptimeCards snapshot={snapshot} />
    <ServiceTable snapshot={snapshot} onRefresh={onRefresh} />
    <IncidentList incidents={snapshot.incidents} />
    <LoadTape snapshot={snapshot} />
    <WebsiteTable sites={snapshot.sites} />
    <FailureList snapshot={snapshot} />
  </div>
)

export const StatusBoard = () => {
  const { snapshot, error, loading, handleRetry, handleRefresh } = useStatusBoard()

  return (
    <div className="view-transition-enter bg-ice min-h-0 min-w-0 flex-1 overflow-y-auto">
      <StaffHeader
        title="Status"
        description="Whether visitors can reach a specialist, and whether the assistant still has knowledge to stand on."
      />
      {error && snapshot === null ? (
        <div id="main-content" className="flex flex-1 items-center justify-center p-6">
          <div className="border-line bg-paper w-full max-w-md rounded-lg border p-6 text-center">
            <p className="text-navy heading text-base">Status could not be loaded.</p>
            <p className="text-mute mt-2 text-sm">Check your connection and try again.</p>
            <Button
              type="button"
              variant="default"
              size="lg"
              className="mt-5 font-bold"
              onClick={handleRetry}
            >
              Retry
            </Button>
          </div>
        </div>
      ) : null}
      {error && snapshot !== null ? (
        <div className="px-5 pt-4 lg:px-8">
          <RetryError text={error} onRetry={handleRetry} className="mt-0" />
        </div>
      ) : null}
      {loading && snapshot === null && error === null ? <StaffPageSkeleton /> : null}
      {snapshot ? <StatusBody snapshot={snapshot} onRefresh={handleRefresh} /> : null}
    </div>
  )
}
