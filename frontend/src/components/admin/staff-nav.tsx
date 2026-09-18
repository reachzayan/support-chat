import { BookOpen, Globe2, Inbox, ScrollText, Table2, type LucideIcon } from "lucide-react"
import Link from "next/link"
import type { ReactNode } from "react"

export type StaffSection = "Inbox" | "Data" | "Knowledge base" | "Sites" | "Logs" | "Settings"

type IconName = "inbox" | "data" | "book" | "globe" | "logs"

type StaffNavProps = {
  current: StaffSection
  displayName: string
}

const LINKS: { href: string; label: StaffSection; icon: IconName }[] = [
  { href: "/admin/inbox", label: "Inbox", icon: "inbox" },
  { href: "/admin/data", label: "Data", icon: "data" },
  { href: "/admin/knowledge", label: "Knowledge base", icon: "book" },
  { href: "/admin/sites", label: "Sites", icon: "globe" },
  { href: "/admin/logs", label: "Logs", icon: "logs" },
]

const ICONS: Record<IconName, LucideIcon> = {
  inbox: Inbox,
  data: Table2,
  book: BookOpen,
  globe: Globe2,
  logs: ScrollText,
}

const Icon = ({ name }: { name: IconName }) => {
  const Component = ICONS[name]
  return <Component aria-hidden="true" className="size-[18px] shrink-0" strokeWidth={1.8} />
}

const Initials = ({ displayName }: { displayName: string }) => {
  const initials = displayName
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase()

  return (
    <span className="bg-ember dark:text-navy-deep flex size-9 shrink-0 items-center justify-center rounded-[8px] text-xs font-bold text-white">
      {initials || "SP"}
    </span>
  )
}

const NavLink = ({
  href,
  label,
  icon,
  current,
}: {
  href: string
  label: StaffSection
  icon: IconName
  current: StaffSection
}) => {
  const active = label === current
  return (
    <Link
      href={href}
      aria-label={label}
      title={label}
      aria-current={active ? "page" : undefined}
      className={`group focus-visible:ring-steel flex size-11 cursor-pointer items-center justify-center rounded-[8px] border-l-2 text-sm font-semibold no-underline transition-colors duration-150 focus-visible:ring-2 focus-visible:outline-none ${
        active
          ? "border-ember bg-paper/10 text-white"
          : "hover:bg-paper/6 border-transparent text-white/65 hover:text-white"
      }`}
    >
      <Icon name={icon} />
      <span className="sr-only">{label}</span>
    </Link>
  )
}

export const StaffNav = ({ current, displayName }: StaffNavProps) => {
  return (
    <aside className="bg-navy-deep flex w-full shrink-0 flex-row border-b border-[#18335C] text-white lg:h-dvh lg:w-[68px] lg:flex-col lg:border-r lg:border-b-0">
      <a
        href="#main-content"
        className="bg-paper text-navy focus-visible:ring-steel sr-only absolute top-3 left-3 z-20 cursor-pointer rounded-[8px] px-3 py-2 text-xs font-bold focus:not-sr-only focus-visible:ring-2 focus-visible:outline-none"
      >
        Skip to content
      </a>
      <div className="border-navy-mid flex items-center justify-center border-r px-3 py-3 lg:border-r-0 lg:border-b lg:py-4">
        <span className="bg-ember dark:text-navy-deep flex size-10 items-center justify-center rounded-[8px] text-xs font-semibold tracking-[-0.08em] text-white">
          Support
        </span>
        <span className="sr-only">SupportChat specialist console</span>
      </div>

      <nav
        aria-label="Primary"
        className="flex flex-1 flex-row gap-1 px-2 py-3 lg:flex-col lg:py-5"
      >
        <p className="sr-only">Workspace</p>
        {LINKS.map((link) => (
          <NavLink key={link.href} {...link} current={current} />
        ))}
      </nav>

      <Link
        href="/admin/settings"
        aria-label={`${displayName} account`}
        title="Account settings"
        className="border-navy-mid focus-visible:ring-steel flex items-center border-l p-2 no-underline outline-none focus-visible:ring-2 lg:border-t lg:border-l-0 lg:p-3"
      >
        <div className="flex items-center justify-center rounded-[8px] p-1">
          <Initials displayName={displayName} />
          <span
            className="relative mt-6 -ml-2 size-2 rounded-full bg-[#67B587]"
            title="Available"
          />
        </div>
        <span className="sr-only">{displayName}</span>
        <span className="sr-only">Operations workspace</span>
      </Link>
    </aside>
  )
}

export const StaffHeader = ({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) => {
  return (
    <header className="border-line bg-paper flex min-h-[82px] items-center justify-between gap-4 border-b px-5 py-4 lg:px-8">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
            {eyebrow}
          </p>
        ) : null}
        <h1 className={`text-navy heading text-[1.65rem] ${eyebrow ? "mt-1" : ""}`}>{title}</h1>
        {description ? <p className="text-mute mt-1 max-w-2xl text-xs">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  )
}
