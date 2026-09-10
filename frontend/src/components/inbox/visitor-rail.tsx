import type { ReactNode } from "react"

import { parseUserAgent, safeHttpUrl } from "@/lib/ua"

import type { ConversationDetail } from "./types"

type VisitorRailProps = {
  detail: ConversationDetail
}

const Fact = ({ label, children }: { label: string; children: ReactNode }) => {
  return (
    <div className="py-3">
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

export const VisitorRail = ({ detail }: VisitorRailProps) => {
  const device = parseUserAgent(detail.visitor.user_agent)
  const assigned = detail.assigned_agent?.display_name ?? "Unassigned"
  return (
    <aside
      aria-label="Visitor facts"
      className="border-line bg-paper flex min-h-0 w-full flex-col overflow-y-auto border-l p-5 lg:w-[300px] lg:shrink-0"
    >
      <div className="border-line mb-2 flex items-center gap-3 border-b pb-4">
        <span className="bg-ice-2 text-steel flex size-10 items-center justify-center rounded-full text-sm font-extrabold">
          {(detail.visitor.name ?? "U").slice(0, 1).toUpperCase()}
        </span>
        <div>
          <p className="text-navy text-sm font-extrabold">Visitor profile</p>
          <p className="text-mute mt-0.5 text-xs">Context for this conversation</p>
        </div>
      </div>
      <VisitorFacts detail={detail} browser={device.browser} os={device.os} assigned={assigned} />
    </aside>
  )
}

const VisitorFacts = ({
  detail,
  browser,
  os,
  assigned,
}: {
  detail: ConversationDetail
  browser: string
  os: string
  assigned: string
}) => (
  <dl className="divide-line divide-y">
    <Fact label="Name">{detail.visitor.name ?? "Unknown"}</Fact>
    <Fact label="Email">{detail.visitor.email ?? "None"}</Fact>
    <Fact label="Phone">{detail.visitor.phone ?? "None"}</Fact>
    <Fact label="Site">{detail.site_name}</Fact>
    <Fact label="Page title">{detail.page.title ?? "None"}</Fact>
    <Fact label="Page URL">
      <UrlValue value={detail.page.url} />
    </Fact>
    <Fact label="Referrer">
      <UrlValue value={detail.page.referrer} />
    </Fact>
    <Fact label="IP">
      <span className="font-mono text-xs">{detail.visitor.ip ?? "None"}</span>
    </Fact>
    <Fact label="Browser">{browser}</Fact>
    <Fact label="OS">{os}</Fact>
    <Fact label="Inquiry type">{detail.inquiry_type ?? "None"}</Fact>
    <Fact label="Assistant intent">{detail.intent ?? "None"}</Fact>
    {detail.attention_needed ? <Fact label="Needs attention">Yes</Fact> : null}
    <Fact label="Assigned specialist">{assigned}</Fact>
  </dl>
)
