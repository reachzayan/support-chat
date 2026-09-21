import { cn } from "cn"
import { ExternalLink } from "lucide-react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { useCallback } from "react"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-new-object-as-prop -- Answer controls close over chunk records; motion props use inline objects. */
import { RetryError } from "@/components/admin/retry-error"
import type { KbPageDetail, KbPageRecord } from "@/components/admin/staff-api"
import { Badge } from "@/components/ui/badge"
import { LinkButton } from "@/components/ui/link-button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import { safeHttpUrl } from "@/lib/ua"

import { humanizeCode } from "./knowledge-format"

const EASE_OUT = [0.23, 1, 0.32, 1] as const
const FADE_UP = { duration: 0.18, ease: EASE_OUT }
const unitKindLabel = (kind: string) => {
  if (kind === "faq") return "FAQ"
  return kind.length > 0 ? `${kind[0].toLocaleUpperCase()}${kind.slice(1)}` : "Unit"
}

const originPagesLabel = (chunk: KbPageDetail["chunks"][number], pages: KbPageRecord[]) => {
  const origins = chunk.origin_urls ?? []
  if (origins.length < 2) {
    return null
  }
  const titles = origins.flatMap((url) => {
    const page = pages.find((item) => item.url === url && item.tab !== "general")
    return page?.title ? [page.title] : []
  })
  if (titles.length === 0) {
    return null
  }
  if (titles.length === 1) {
    return `Also on ${titles[0]}`
  }
  if (titles.length === 2) {
    return `Also on ${titles[0]} and ${titles[1]}`
  }
  return `Also on ${titles.slice(0, -1).join(", ")}, and ${titles[titles.length - 1]}`
}
export const DetailPane = ({
  detail,
  pages,
  hasSource,
  isAdmin,
  pendingIds,
  errors,
  notice,
  onTogglePage,
  onRetryPage,
  onToggleChunk,
}: {
  detail: KbPageDetail | null
  pages: KbPageRecord[]
  hasSource: boolean
  isAdmin: boolean
  pendingIds: string[]
  errors: Record<string, string>
  notice: string
  onTogglePage: (page: KbPageRecord) => void
  onRetryPage: (page: KbPageRecord) => void
  onToggleChunk: (pageId: string, chunk: KbPageDetail["chunks"][number]) => Promise<void>
}) => (
  <section className="bg-paper flex min-h-0 min-w-0 flex-1 flex-col">
    <div className="flex h-14 items-center px-5">
      <h2 className="text-navy heading text-sm">Retrieved answers</h2>
    </div>
    <ScrollArea className="min-h-0 flex-1">
      {detail ? (
        <PageInspection
          detail={detail}
          pages={pages}
          isAdmin={isAdmin}
          pendingIds={pendingIds}
          errors={errors}
          notice={notice}
          onTogglePage={onTogglePage}
          onRetryPage={onRetryPage}
          onToggle={onToggleChunk}
        />
      ) : (
        <p className="text-mute px-5 py-8 text-sm">
          {hasSource
            ? "Select a page to inspect retrieved answers."
            : "Add a source to get started."}
        </p>
      )}
    </ScrollArea>
  </section>
)

const PageRowActions = ({
  page,
  onToggle,
  onRetry,
}: {
  page: KbPageRecord
  onToggle: (page: KbPageRecord) => void
  onRetry: (page: KbPageRecord) => void
}) => {
  const handleToggle = useCallback(() => onToggle(page), [onToggle, page])
  const handleRetry = useCallback(() => onRetry(page), [onRetry, page])
  return (
    <div className="flex items-center gap-3">
      {page.processing_status === "failed" ? (
        <LinkButton type="button" onClick={handleRetry}>
          Retry page
        </LinkButton>
      ) : null}
      <LinkButton
        type="button"
        variant={page.enabled ? "emphasis" : "default"}
        onClick={handleToggle}
        aria-label={page.enabled ? "Disable page" : "Enable page"}
      >
        {page.enabled ? "Disable" : "Enable"}
      </LinkButton>
    </div>
  )
}

const InspectionHeader = ({
  detail,
  isAdmin,
  onTogglePage,
  onRetryPage,
}: {
  detail: KbPageDetail
  isAdmin: boolean
  onTogglePage: (page: KbPageRecord) => void
  onRetryPage: (page: KbPageRecord) => void
}) => {
  const href = safeHttpUrl(detail.url)
  return (
    <div className="mb-4 flex flex-col gap-1">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
            {detail.tab === "general" ? "Shared answers" : "Page inspection"}
          </p>
          <h3 className="text-navy heading text-base">{detail.title}</h3>
        </div>
        {isAdmin && detail.tab !== "general" ? (
          <PageRowActions page={detail} onToggle={onTogglePage} onRetry={onRetryPage} />
        ) : null}
      </div>
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noreferrer noopener"
          className="text-steel hover:text-navy decoration-steel/40 inline-flex w-fit items-center gap-1.5 font-mono text-xs underline underline-offset-4 transition-colors duration-150"
        >
          {detail.url}
          <ExternalLink aria-hidden="true" className="size-3.5" />
        </a>
      ) : (
        <p className="text-mute font-mono text-xs">{detail.url}</p>
      )}
      <p className="text-mute mt-2 text-xs font-semibold">
        {detail.chunks.filter((chunk) => chunk.enabled).length} of {detail.chunks.length} answers
        enabled
      </p>
    </div>
  )
}

const InspectionNotices = ({ detail, notice }: { detail: KbPageDetail; notice: string }) => (
  <>
    {detail.skip_reason ? (
      <p className="text-ember mt-2 text-sm">Skipped: {humanizeCode(detail.skip_reason)}</p>
    ) : null}
    {detail.failure_reason && detail.failure_reason !== detail.skip_reason ? (
      <p className="text-ember mt-2 text-sm">Failed: {humanizeCode(detail.failure_reason)}</p>
    ) : null}
    {notice ? <output className="text-ember mt-3 block text-sm">{notice}</output> : null}
  </>
)

const AnswerUnit = ({
  pageId,
  pages,
  chunk,
  isAdmin,
  pending,
  error,
  onToggle,
}: {
  pageId: string
  pages: KbPageRecord[]
  chunk: KbPageDetail["chunks"][number]
  isAdmin: boolean
  pending: boolean
  error: string | undefined
  onToggle: (pageId: string, chunk: KbPageDetail["chunks"][number]) => Promise<void>
}) => {
  const originLabel = originPagesLabel(chunk, pages)
  return (
    <article className={cn("py-4 transition-opacity duration-150", !chunk.enabled && "opacity-60")}>
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-navy heading text-sm">{chunk.heading}</h4>
        <div className="flex shrink-0 items-center gap-2">
          <Badge className="bg-ice-2 text-steel">{unitKindLabel(chunk.kind)}</Badge>
          <Badge className={chunk.enabled ? "bg-[#E8F5EE] text-[#247A4D]" : "bg-ice-2 text-mute"}>
            {chunk.enabled ? "Enabled" : "Disabled"}
          </Badge>
          <span className="text-mute font-mono text-[10px]">#{chunk.ordinal + 1}</span>
        </div>
      </div>
      <p className="text-ink mt-2 text-sm leading-6 whitespace-pre-wrap">{chunk.body}</p>
      {originLabel ? <p className="text-mute mt-2 text-xs">{originLabel}</p> : null}
      {isAdmin ? (
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="text-mute text-xs font-bold">Include in answers</span>
          <Switch
            aria-label={`Include ${chunk.heading} in answers`}
            checked={chunk.enabled}
            disabled={pending}
            onCheckedChange={() => void onToggle(pageId, chunk)}
          />
        </div>
      ) : null}
      {error ? (
        <RetryError text={error} className="mt-3" onRetry={() => void onToggle(pageId, chunk)} />
      ) : null}
    </article>
  )
}

const PageInspection = ({
  detail,
  pages,
  isAdmin,
  pendingIds,
  errors,
  notice,
  onTogglePage,
  onRetryPage,
  onToggle,
}: {
  detail: KbPageDetail
  pages: KbPageRecord[]
  isAdmin: boolean
  pendingIds: string[]
  errors: Record<string, string>
  notice: string
  onTogglePage: (page: KbPageRecord) => void
  onRetryPage: (page: KbPageRecord) => void
  onToggle: (pageId: string, chunk: KbPageDetail["chunks"][number]) => Promise<void>
}) => {
  const reducedMotion = useReducedMotion()
  return (
    <AnimatePresence mode="wait">
      <motion.section
        key={detail.id}
        initial={reducedMotion ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reducedMotion ? undefined : { opacity: 0, y: 6 }}
        transition={FADE_UP}
        className="px-5 pt-2 pb-8"
      >
        <InspectionHeader
          detail={detail}
          isAdmin={isAdmin}
          onTogglePage={onTogglePage}
          onRetryPage={onRetryPage}
        />
        <InspectionNotices detail={detail} notice={notice} />
        {detail.chunks.length === 0 ? (
          <p className="text-mute mt-4 text-sm">No retrieved answers on this page yet.</p>
        ) : (
          <div className="divide-line mt-2 divide-y">
            {detail.chunks.map((chunk) => (
              <AnswerUnit
                key={chunk.id}
                pageId={detail.id}
                pages={pages}
                chunk={chunk}
                isAdmin={isAdmin}
                pending={pendingIds.includes(chunk.id)}
                error={errors[chunk.id]}
                onToggle={onToggle}
              />
            ))}
          </div>
        )}
      </motion.section>
    </AnimatePresence>
  )
}
