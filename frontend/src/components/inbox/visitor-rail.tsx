"use client"

import { ChevronDown } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"
import { useCallback, useMemo, useState, type ReactNode } from "react"

import { BlockVisitorDialog } from "@/components/admin/block-visitor-dialog"
import { staffWrite } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { parseUserAgent, safeHttpUrl } from "@/lib/ua"

import type { ConversationDetail } from "./types"

type VisitorRailProps = {
  detail: ConversationDetail
  showHeader?: boolean
}

const CHEVRON_SPRING = { type: "spring", stiffness: 420, damping: 28, mass: 0.55 } as const
const ZERO_TRANSITION = { duration: 0 }
const CHEVRON_OPEN = { rotate: 180 }
const CHEVRON_CLOSED = { rotate: 0 }

const Fact = ({ label, children }: { label: string; children: ReactNode }) => {
  return (
    <div className="border-line/70 grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3 border-b py-2.5 last:border-b-0">
      <dt className="text-mute pt-0.5 text-[10px] font-semibold tracking-[0.12em] uppercase">
        {label}
      </dt>
      <dd className="text-ink min-w-0 text-sm leading-5 [overflow-wrap:anywhere]">{children}</dd>
    </div>
  )
}

const UrlValue = ({ value }: { value: string | null }) => {
  if (!value) {
    return <span className="text-mute">None</span>
  }
  const href = safeHttpUrl(value)
  if (href === null) {
    return <span className="break-all">{value}</span>
  }
  return (
    <a
      href={href}
      rel="noreferrer noopener"
      title={value}
      className="text-steel focus-visible:ring-steel block cursor-pointer truncate underline focus-visible:ring-2 focus-visible:outline-none"
    >
      {value}
    </a>
  )
}

const RailSection = ({
  title,
  defaultOpen = true,
  children,
}: {
  title: string
  defaultOpen?: boolean
  children: ReactNode
}) => {
  const [open, setOpen] = useState(defaultOpen)
  const reducedMotion = useReducedMotion()
  const chevronTransition = reducedMotion ? ZERO_TRANSITION : CHEVRON_SPRING
  const chevronAnimate = open ? CHEVRON_OPEN : CHEVRON_CLOSED
  const handleOpenChange = useCallback((next: boolean) => {
    setOpen(next)
  }, [])
  return (
    <Collapsible
      open={open}
      onOpenChange={handleOpenChange}
      className="border-line border-b last:border-b-0"
    >
      <h2>
        <CollapsibleTrigger
          aria-label={title}
          className="group text-navy hover:bg-ice-2 h-11 w-full justify-between rounded-none px-4 text-left text-[10px] font-bold tracking-[0.14em] uppercase aria-expanded:bg-transparent"
        >
          <span>{title}</span>
          <motion.span
            aria-hidden="true"
            className="inline-flex"
            animate={chevronAnimate}
            transition={chevronTransition}
          >
            <ChevronDown className="size-3.5" aria-hidden="true" />
          </motion.span>
        </CollapsibleTrigger>
      </h2>
      <CollapsibleContent className="mt-0 px-4 pb-4">
        <dl>{children}</dl>
      </CollapsibleContent>
    </Collapsible>
  )
}

const orNone = (value: string | null) => value ?? "None"

const META_PILL =
  "bg-ice-2 text-mute inline-flex shrink-0 items-center rounded-full px-2 py-1 text-[10px] font-bold"

const VisitorRailHeader = ({
  name,
  siteName,
  closed,
  visible,
}: {
  name: string
  siteName: string
  closed: boolean
  visible: boolean
}) =>
  visible ? (
    <div className="border-line bg-paper flex h-16 shrink-0 items-center gap-3 border-b px-5">
      <span className="bg-ice-2 text-steel flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold">
        {name.slice(0, 1).toUpperCase()}
      </span>
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <p className="text-navy heading truncate text-sm">{name}</p>
          {closed ? (
            <span className={`${META_PILL} tracking-[0.08em] uppercase`}>Closed</span>
          ) : null}
        </div>
        <p className="text-mute mt-0.5 flex items-center gap-1.5 truncate text-xs">
          <span className="size-1.5 rounded-full bg-[#67B587]" />
          {siteName}
        </p>
      </div>
    </div>
  ) : null

const ContactSection = ({
  detail,
  blocked,
  pendingUnblock,
  onBlock,
  onUnblock,
}: {
  detail: ConversationDetail
  blocked: boolean
  pendingUnblock: boolean
  onBlock: () => void
  onUnblock: () => void
}) => (
  <RailSection title="Contact">
    <Fact label="Email">
      <span className="break-all">{orNone(detail.visitor.email)}</span>
    </Fact>
    <Fact label="Phone">{orNone(detail.visitor.phone)}</Fact>
    <Fact label="IP">
      <span className="font-mono text-xs">{orNone(detail.visitor.ip)}</span>
    </Fact>
    <Fact label="Location">{detail.visitor.location ?? "Not available yet"}</Fact>
    <div className="pt-3 pb-1">
      <BlockToggle
        blocked={blocked}
        pendingUnblock={pendingUnblock}
        onBlock={onBlock}
        onUnblock={onUnblock}
      />
    </div>
  </RailSection>
)

const BlockToggle = ({
  blocked,
  pendingUnblock,
  onBlock,
  onUnblock,
}: {
  blocked: boolean
  pendingUnblock: boolean
  onBlock: () => void
  onUnblock: () => void
}) => {
  if (blocked) {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={onUnblock}
        disabled={pendingUnblock}
        aria-label="Unblock visitor"
        className="border-line text-navy hover:bg-ice-2 w-full font-bold"
      >
        Unblock visitor
      </Button>
    )
  }
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onBlock}
      aria-label="Block visitor"
      className="border-line text-navy hover:bg-ice-2 w-full font-bold"
    >
      Block visitor
    </Button>
  )
}

const ConversationSection = ({
  detail,
  assigned,
}: {
  detail: ConversationDetail
  assigned: string
}) => (
  <RailSection title="Conversation">
    <Fact label="Inquiry type">{orNone(detail.inquiry_type)}</Fact>
    <Fact label="Assistant intent">{orNone(detail.intent)}</Fact>
    {detail.attention_needed ? <Fact label="Needs attention">Yes</Fact> : null}
    <Fact label="Assigned specialist">{assigned}</Fact>
  </RailSection>
)

const PageSection = ({ detail }: { detail: ConversationDetail }) => (
  <RailSection title="Page context">
    <Fact label="Page title">{orNone(detail.page.title)}</Fact>
    <Fact label="Page URL">
      <UrlValue value={detail.page.url} />
    </Fact>
    <Fact label="Referrer">
      <UrlValue value={detail.page.referrer} />
    </Fact>
  </RailSection>
)

const TechnicalSection = ({ browser, os }: { browser: string; os: string }) => (
  <RailSection title="Technical">
    <Fact label="Browser">{browser}</Fact>
    <Fact label="OS">{os}</Fact>
  </RailSection>
)

// oxlint-disable-next-line eslint/max-lines-per-function -- Block overlay, unblock, and dialog stay with the rail.
export const VisitorRail = ({ detail, showHeader = true }: VisitorRailProps) => {
  const device = parseUserAgent(detail.visitor.user_agent)
  const assigned = detail.assigned_agent?.display_name ?? "Unassigned"
  const name = detail.visitor.name ?? "Unknown visitor"
  const [blockOpen, setBlockOpen] = useState(false)
  const [announcement, setAnnouncement] = useState("")
  const [pendingUnblock, setPendingUnblock] = useState(false)
  const [overlay, setOverlay] = useState<{ blocked: boolean; blockId: string | null } | null>(null)
  const blocked = overlay?.blocked ?? detail.blocked
  const blockId = overlay?.blockId ?? detail.block_id
  const handleOpenBlock = useCallback(() => setBlockOpen(true), [])
  const handleCloseBlock = useCallback(() => setBlockOpen(false), [])
  const handleBlocked = useCallback((nextBlockId: string) => {
    setBlockOpen(false)
    setOverlay({ blocked: true, blockId: nextBlockId })
    setAnnouncement("Visitor blocked.")
  }, [])
  const handleUnblock = useCallback(async () => {
    if (!blockId || pendingUnblock) {
      return
    }
    setPendingUnblock(true)
    try {
      const response = await staffWrite(`/api/visitor-blocks/${blockId}`, "DELETE", {})
      if (!response.ok) {
        setAnnouncement("The visitor could not be unblocked. Try again.")
        return
      }
      setOverlay({ blocked: false, blockId: null })
      setAnnouncement("Visitor unblocked.")
    } catch {
      setAnnouncement("The visitor could not be unblocked. Try again.")
    } finally {
      setPendingUnblock(false)
    }
  }, [blockId, pendingUnblock])
  const handleUnblockClick = useCallback(() => {
    void handleUnblock()
  }, [handleUnblock])
  const blockTarget = useMemo(
    () => ({
      siteId: detail.site_id,
      visitorName: name,
      email: detail.visitor.email,
      phone: detail.visitor.phone,
      ip: detail.visitor.ip,
    }),
    [detail.site_id, detail.visitor.email, detail.visitor.ip, detail.visitor.phone, name],
  )
  return (
    <aside
      aria-label="Visitor facts"
      className="border-line bg-paper flex min-h-0 w-full flex-col overflow-hidden border-l lg:w-[320px] lg:shrink-0"
    >
      <VisitorRailHeader
        visible={showHeader}
        name={name}
        siteName={detail.site_name}
        closed={detail.state === "closed"}
      />
      <section
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-3"
        aria-label="Visitor information"
      >
        <ContactSection
          detail={detail}
          blocked={blocked}
          pendingUnblock={pendingUnblock}
          onBlock={handleOpenBlock}
          onUnblock={handleUnblockClick}
        />
        <ConversationSection detail={detail} assigned={assigned} />
        <PageSection detail={detail} />
        <TechnicalSection browser={device.browser} os={device.os} />
      </section>
      {blockOpen ? (
        <BlockVisitorDialog
          key={detail.id}
          target={blockTarget}
          onClose={handleCloseBlock}
          onBlocked={handleBlocked}
        />
      ) : null}
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </aside>
  )
}
