import { ChevronDown } from "lucide-react"
import type { ReactNode } from "react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { parseUserAgent, safeHttpUrl } from "@/lib/ua"

import type { ConversationDetail } from "./types"

type VisitorRailProps = {
  detail: ConversationDetail
}

const Fact = ({ label, children }: { label: string; children: ReactNode }) => {
  return (
    <div>
      <dt className="text-mute text-[10px] font-medium tracking-[0.12em] uppercase">{label}</dt>
      <dd className="text-ink mt-1 text-sm leading-5 break-words">{children}</dd>
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
}) => (
  <Collapsible defaultOpen={defaultOpen} className="border-line border-b pb-1 last:border-b-0">
    <CollapsibleTrigger
      aria-label={title}
      className="group text-mute hover:text-ink flex w-full items-center justify-between px-5 py-3 text-left text-[10px] font-bold tracking-[0.12em] uppercase focus-visible:ring-0"
    >
      <span>{title}</span>
      <ChevronDown
        aria-hidden="true"
        className="size-3.5 transition-transform duration-150 group-aria-expanded:rotate-180"
      />
    </CollapsibleTrigger>
    <CollapsibleContent className="mt-0 px-5 pb-1">
      <dl className="flex flex-col gap-3">{children}</dl>
    </CollapsibleContent>
  </Collapsible>
)

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
  <div className="border-line flex h-16 items-center gap-3 border-b px-5">
    <span className="bg-ice-2 text-steel flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold">
      {name.slice(0, 1).toUpperCase()}
    </span>
    <div className="min-w-0">
      <div className="flex min-w-0 items-center gap-2">
        <p className="text-navy truncate text-sm font-extrabold tracking-[-0.02em]">{name}</p>
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
      className="border-line bg-paper flex min-h-0 w-full flex-col overflow-y-auto border-l lg:w-[300px] lg:shrink-0"
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
