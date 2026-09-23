"use client"

import { ChevronDown } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"
import { useCallback, useState, type ReactNode } from "react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { parseUserAgent, safeHttpUrl } from "@/lib/ua"

import type { ConversationDetail } from "./types"

type VisitorRailProps = {
  detail: ConversationDetail
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
      <dd className="text-ink min-w-0 text-sm leading-5 break-words">{children}</dd>
    </div>
  )
}

const UrlValue = ({ value }: { value: string | null }) => {
  if (!value) {
    return <span className="text-mute">None</span>
  }
  const href = safeHttpUrl(value)
  if (href === null) {
    return <span>{value}</span>
  }
  return (
    <a href={href} rel="noreferrer noopener" className="text-steel cursor-pointer underline">
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
      className="border-line bg-paper mx-3 mt-3 overflow-hidden rounded-lg border"
    >
      <CollapsibleTrigger
        aria-label={title}
        className="group text-navy hover:bg-ice-2 h-11 w-full justify-between rounded-none px-3.5 text-left text-[10px] font-bold tracking-[0.14em] uppercase aria-expanded:bg-transparent"
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
      <CollapsibleContent className="mt-0 px-3 pb-2">
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
}: {
  name: string
  siteName: string
  closed: boolean
}) => (
  <div className="border-line bg-paper flex h-16 shrink-0 items-center gap-3 border-b px-5">
    <span className="bg-ice-2 text-steel flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold">
      {name.slice(0, 1).toUpperCase()}
    </span>
    <div className="min-w-0">
      <div className="flex min-w-0 items-center gap-2">
        <p className="text-navy heading truncate text-sm">{name}</p>
        {closed ? <span className={`${META_PILL} tracking-[0.08em] uppercase`}>Closed</span> : null}
      </div>
      <p className="text-mute mt-0.5 flex items-center gap-1.5 truncate text-xs">
        <span className="size-1.5 rounded-full bg-[#67B587]" />
        {siteName}
      </p>
    </div>
  </div>
)

const ContactSection = ({ detail }: { detail: ConversationDetail }) => (
  <RailSection title="Contact">
    <Fact label="Email">{orNone(detail.visitor.email)}</Fact>
    <Fact label="Phone">{orNone(detail.visitor.phone)}</Fact>
    <Fact label="IP">
      <span className="font-mono text-xs">{orNone(detail.visitor.ip)}</span>
    </Fact>
    <Fact label="Location">{orNone(detail.visitor.location)}</Fact>
  </RailSection>
)

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

export const VisitorRail = ({ detail }: VisitorRailProps) => {
  const device = parseUserAgent(detail.visitor.user_agent)
  const assigned = detail.assigned_agent?.display_name ?? "Unassigned"
  const name = detail.visitor.name ?? "Unknown visitor"
  return (
    <aside
      aria-label="Visitor facts"
      className="border-line bg-ice/60 flex min-h-0 w-full flex-col overflow-y-auto border-l pb-3 lg:w-[320px] lg:shrink-0"
    >
      <VisitorRailHeader
        name={name}
        siteName={detail.site_name}
        closed={detail.state === "closed"}
      />
      <ContactSection detail={detail} />
      <ConversationSection detail={detail} assigned={assigned} />
      <PageSection detail={detail} />
      <TechnicalSection browser={device.browser} os={device.os} />
    </aside>
  )
}
