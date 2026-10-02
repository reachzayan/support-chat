export type ServiceState = "ok" | "down" | "silent"
export type OverallState = "ok" | "attention" | "degraded"
export type KnowledgeTone = "none" | "ready" | "queued" | "running" | "failed"

export type StatusServices = {
  api: ServiceState
  postgres: ServiceState
  redis: ServiceState
  worker: ServiceState
}

export type StatusSite = {
  id: string
  key: string
  name: string
  enabled: boolean
  bot_enabled: boolean
  human_enabled: boolean
  widget_installed: boolean | null
  waiting: number
  knowledge: KnowledgeTone
}

export type StatusError = {
  id: string
  created_at: string
  event: string
  message: string
  source: string
}

export type AvailabilityTone = "empty" | "up" | "degraded"

export type StatusMonitor = {
  key: string
  name: string
  state: ServiceState
  availability_30d: AvailabilityTone[]
  latency_24h: (number | null)[]
}

export type StatusIncident = {
  date: string
  summary: string
}

export type StatusSnapshot = {
  checked_at: string
  overall: OverallState
  headline: string
  services: StatusServices
  live: { visitors: number; specialists: number }
  inbox: { waiting: number; bot: number; live: number; closed_today: number }
  knowledge: { ready: number; running: number; failed: number; queued: number }
  gaps_open: number
  errors_24h: number
  recent_errors: StatusError[]
  sites: StatusSite[]
  uptime: {
    hours_24: number | null
    days_7: number | null
    days_30: number | null
    days_90: number | null
  }
  monitors: StatusMonitor[]
  incidents: StatusIncident[]
}

export const SERVICE_ORDER = ["api", "postgres", "redis", "worker"] as const

export const serviceLabel = (key: (typeof SERVICE_ORDER)[number]) => {
  if (key === "api") {
    return "API"
  }
  if (key === "postgres") {
    return "Postgres"
  }
  if (key === "redis") {
    return "Redis"
  }
  return "Background work"
}

export const serviceTone = (state: ServiceState) => {
  if (state === "ok") {
    return "Answering"
  }
  if (state === "down") {
    return "Down"
  }
  return "Silent"
}

export const widgetLabel = (installed: boolean | null) => {
  if (installed === true) {
    return "Installed"
  }
  if (installed === false) {
    return "Missing"
  }
  return "Not seen"
}

export const knowledgeLabel = (tone: KnowledgeTone) => {
  if (tone === "failed") {
    return "Failed"
  }
  if (tone === "ready") {
    return "Ready"
  }
  if (tone === "running") {
    return "Running"
  }
  if (tone === "queued") {
    return "Queued"
  }
  return "None"
}

export const waitingLabel = (count: number) => {
  if (count === 1) {
    return "1 waiting"
  }
  return `${count} waiting`
}

export const visitorLine = (count: number) => {
  if (count === 1) {
    return "1 visitor on the widget"
  }
  return `${count} visitors on the widget`
}

export const specialistLine = (count: number) => {
  if (count === 1) {
    return "1 specialist connected"
  }
  return `${count} specialists connected`
}

export const unansweredLine = (count: number) => {
  if (count === 1) {
    return "1 unanswered question"
  }
  return `${count} unanswered questions`
}

export const failuresHeading = (count: number) => {
  if (count === 0) {
    return "No failures in the last 24 hours"
  }
  if (count === 1) {
    return "1 failure in the last 24 hours"
  }
  return `${count} failures in the last 24 hours`
}

export const assistantLabel = (enabled: boolean) => {
  if (enabled) {
    return "On"
  }
  return "Off"
}

export const formatUptime = (value: number | null) => {
  if (value === null) {
    return "—"
  }
  if (Number.isInteger(value)) {
    return `${value}%`
  }
  return `${value.toFixed(1)}%`
}

export const formatCheckedAt = (iso: string) => {
  const stamp = new Date(iso)
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ]
  const day = String(stamp.getUTCDate()).padStart(2, "0")
  const hour = String(stamp.getUTCHours()).padStart(2, "0")
  const minute = String(stamp.getUTCMinutes()).padStart(2, "0")
  return `${day} ${months[stamp.getUTCMonth()]} ${stamp.getUTCFullYear()}, ${hour}:${minute} UTC`
}

const countPhrase = (count: number, one: string, many: string) => {
  if (count === 1) {
    return `1 ${one}`
  }
  return `${count} ${many}`
}

export const availabilityLabel = (days: AvailabilityTone[]) => {
  const up = days.filter((day) => day === "up").length
  const degraded = days.filter((day) => day === "degraded").length
  const empty = days.filter((day) => day === "empty").length
  const parts: string[] = []
  if (up > 0) {
    parts.push(countPhrase(up, "day answering", "days answering"))
  }
  if (degraded > 0) {
    parts.push(countPhrase(degraded, "day degraded", "days degraded"))
  }
  if (empty > 0) {
    parts.push(countPhrase(empty, "day with no sample", "days with no sample"))
  }
  if (parts.length === 0) {
    return "Availability last 30 days"
  }
  return `Availability last 30 days: ${parts.join(", ")}`
}

export const latencyLabel = (hours: (number | null)[]) => {
  const values = hours.filter((hour): hour is number => hour !== null)
  if (values.length === 0) {
    return "Median response last 24 hours, no samples"
  }
  return `Median response last 24 hours, peak ${Math.max(...values)} milliseconds`
}

export const SPARK_WIDTH = 120
export const SPARK_HEIGHT = 32
const SPARK_PAD = 3
const SPARK_PLOT = SPARK_HEIGHT - SPARK_PAD - 2

type SparkPoint = { x: number; y: number }

const sparkX = (index: number) => (index / 23) * SPARK_WIDTH

const fmt = (value: number) => value.toFixed(1)

const heldHours = (hours: (number | null)[]) => {
  const series: { index: number; value: number }[] = []
  let last: number | null = null
  hours.forEach((hour, index) => {
    if (hour !== null) {
      last = hour
    }
    if (last !== null) {
      series.push({ index, value: last })
    }
  })
  return series
}

const sparkCoords = (series: { index: number; value: number }[]) => {
  const peak = Math.max(...series.map((row) => row.value), 1)
  return series.map((row) => ({
    x: sparkX(row.index),
    y: SPARK_PAD + (1 - row.value / peak) * SPARK_PLOT,
  }))
}

const sparkSegment = (points: SparkPoint[], index: number) => {
  const previous = points[Math.max(0, index - 1)]
  const start = points[index]
  const end = points[index + 1]
  const next = points[Math.min(points.length - 1, index + 2)]
  const c1x = start.x + (end.x - previous.x) / 6
  const c1y = start.y + (end.y - previous.y) / 6
  const c2x = end.x - (next.x - start.x) / 6
  const c2y = end.y - (next.y - start.y) / 6
  return ` C ${fmt(c1x)} ${fmt(c1y)}, ${fmt(c2x)} ${fmt(c2y)}, ${fmt(end.x)} ${fmt(end.y)}`
}

const sparkLine = (points: SparkPoint[]) => {
  if (points.length === 1) {
    const left = Math.max(0, points[0].x - sparkX(1))
    return `M ${fmt(left)} ${fmt(points[0].y)} L ${fmt(points[0].x)} ${fmt(points[0].y)}`
  }
  if (points.length === 2) {
    return `M ${fmt(points[0].x)} ${fmt(points[0].y)} L ${fmt(points[1].x)} ${fmt(points[1].y)}`
  }
  return points.slice(0, -1).reduce((path, _point, index) => {
    if (index === 0) {
      return `M ${fmt(points[0].x)} ${fmt(points[0].y)}${sparkSegment(points, 0)}`
    }
    return `${path}${sparkSegment(points, index)}`
  }, "")
}

const sparkArea = (line: string, points: SparkPoint[]) => {
  const last = points[points.length - 1]
  const left = points.length === 1 ? Math.max(0, last.x - sparkX(1)) : points[0].x
  return `${line} L ${fmt(last.x)} ${fmt(SPARK_HEIGHT)} L ${fmt(left)} ${fmt(SPARK_HEIGHT)} Z`
}

export const latencySparkPath = (hours: (number | null)[]) => {
  const series = heldHours(hours)
  if (series.length === 0) {
    return null
  }
  const points = sparkCoords(series)
  const line = sparkLine(points)
  return { line, area: sparkArea(line, points) }
}
