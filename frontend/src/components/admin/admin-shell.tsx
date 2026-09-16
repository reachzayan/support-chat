/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-object-as-prop */

"use client"

import { cn } from "cn"
import {
  BookOpen,
  MessageSquareText,
  ChevronDown,
  Globe2,
  Inbox,
  ScrollText,
  Table2,
  type LucideIcon,
} from "lucide-react"
import { motion } from "motion/react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react"

import { ClientErrorReporter } from "@/components/admin/client-error-reporter"
import { StaffPageSkeleton } from "@/components/admin/loading-skeleton"
import { usePreferences } from "@/components/preferences-context"
import { ThemeToggle } from "@/components/theme-toggle"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { refreshSession, type StaffUser } from "@/lib/auth-client"

const MotionLink = motion.create(Link)

const AdminUserContext = createContext<StaffUser | null>(null)

export const useAdminUser = () => {
  const user = useContext(AdminUserContext)
  if (user === null) {
    throw new Error("useAdminUser must be used within AdminShell.")
  }
  return user
}

type AdminLink = {
  href: string
  label: string
  icon: LucideIcon
}

const workspaceLinks: AdminLink[] = [
  { href: "/admin/inbox", label: "Inbox", icon: Inbox },
  { href: "/admin/data", label: "Data", icon: Table2 },
  { href: "/admin/knowledge", label: "Knowledge base", icon: BookOpen },
  { href: "/admin/canned-responses", label: "Canned responses", icon: MessageSquareText },
  { href: "/admin/sites", label: "Sites", icon: Globe2 },
  { href: "/admin/logs", label: "Logs", icon: ScrollText },
]

const initialsFor = (displayName: string) =>
  displayName
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase() || "SP"

const NAV_SPRING = { type: "spring", stiffness: 500, damping: 42, mass: 0.6 } as const

const AvatarMark = ({ initials }: { initials: string }) => (
  <span className="relative flex size-7 shrink-0 items-center justify-center">
    <span className="bg-sidebar-accent flex size-7 items-center justify-center rounded-[8px] text-[10px] leading-none font-bold text-white">
      {initials}
    </span>
    <span
      aria-hidden="true"
      className="border-sidebar absolute -right-0.5 -bottom-0.5 size-2 rounded-full border-2 bg-[#67B587]"
    />
  </span>
)

const AdminSidebarLink = ({
  href,
  label,
  icon: Icon,
  active,
  collapsed,
}: AdminLink & { active: boolean; collapsed: boolean }) => (
  <SidebarMenuItem className={cn("flex w-full", collapsed && "justify-center")}>
    <SidebarMenuButton
      isActive={active}
      tooltip={label}
      render={
        <MotionLink
          href={href}
          aria-label={label}
          whileHover={collapsed ? undefined : { x: 2 }}
          whileTap={{ scale: 0.96 }}
          className="cursor-pointer no-underline"
        />
      }
      className={cn(
        "text-sidebar-foreground/60 data-active:text-sidebar-foreground relative isolate h-11 rounded-[10px] px-3 text-sm font-semibold no-underline transition-[width,height,padding,colors] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-white/4.5 hover:text-sidebar-foreground/90 data-active:hover:bg-transparent",
        collapsed && "size-8! justify-center gap-0 p-0!",
      )}
    >
      {active ? (
        <motion.span
          layoutId="admin-nav-active"
          transition={NAV_SPRING}
          aria-hidden="true"
          className={cn(
            "absolute inset-0 -z-10 rounded-[10px]",
            collapsed
              ? "bg-ember/15"
              : "from-ember/20 via-ember/8 bg-linear-to-r to-transparent ring-1 ring-white/5",
          )}
        />
      ) : null}
      {active && !collapsed ? (
        <span
          aria-hidden="true"
          className="bg-ember absolute top-2 bottom-2 left-0 -z-10 w-0.5 rounded-full"
        />
      ) : null}
      <Icon aria-hidden="true" className="size-4.5 shrink-0" strokeWidth={1.8} />
      {!collapsed ? <span className="min-w-0 truncate">{label}</span> : null}
    </SidebarMenuButton>
  </SidebarMenuItem>
)

const AdminSidebarLinks = ({
  links,
  pathname,
  collapsed,
}: {
  links: AdminLink[]
  pathname: string
  collapsed: boolean
}) => (
  <SidebarMenu className={cn("w-full gap-1", collapsed && "items-center")}>
    {links.map((link) => (
      <AdminSidebarLink
        key={link.href}
        {...link}
        collapsed={collapsed}
        active={pathname === link.href || pathname.startsWith(`${link.href}/`)}
      />
    ))}
  </SidebarMenu>
)

const AdminSidebarAccount = ({
  displayName,
  pathname,
  collapsed,
}: {
  displayName: string
  pathname: string
  collapsed: boolean
}) => {
  const initials = initialsFor(displayName)
  const accountLabel = `${displayName} account`
  const active = pathname === "/admin/settings"

  if (collapsed) {
    return (
      <SidebarMenuItem className="flex justify-center">
        <Tooltip>
          <TooltipTrigger
            render={
              <Link
                href="/admin/settings"
                aria-label={accountLabel}
                data-active={active || undefined}
                className={cn(
                  "flex size-8 items-center justify-center rounded-[10px] no-underline outline-none transition-colors hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-[#70B8FF]",
                  active && "bg-ember/15",
                )}
              />
            }
          >
            <AvatarMark initials={initials} />
          </TooltipTrigger>
          <TooltipContent side="right" align="center">
            {displayName}
          </TooltipContent>
        </Tooltip>
      </SidebarMenuItem>
    )
  }

  return (
    <SidebarMenuItem className="flex w-full">
      <SidebarMenuButton
        size="lg"
        tooltip={displayName}
        isActive={active}
        render={<Link href="/admin/settings" aria-label={accountLabel} />}
        className="text-sidebar-foreground rounded-[10px] px-2 no-underline hover:bg-white/5"
      >
        <AvatarMark initials={initials} />
        <span className="grid min-w-0 flex-1 text-left text-xs">
          <span className="truncate font-bold text-white">{displayName}</span>
          <span className="truncate text-[10px] text-white/50">Accepting chats</span>
        </span>
        <ChevronDown aria-hidden="true" className="ml-auto size-4 shrink-0 text-white/40" />
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

const adminSidebarStyle = {
  "--sidebar": "#14161b",
  "--sidebar-foreground": "#F4F8FF",
  "--sidebar-accent": "#1e212a",
  "--sidebar-accent-foreground": "#FFFFFF",
  "--sidebar-border": "transparent",
  "--sidebar-ring": "#70B8FF",
} as CSSProperties

const AdminSidebarBrand = ({ collapsed }: { collapsed: boolean }) => (
  <SidebarHeader
    className={cn(
      "flex h-14 shrink-0 flex-col justify-center px-3",
      collapsed && "items-center px-0 py-2",
    )}
  >
    <Link
      href="/admin/inbox"
      aria-label="SupportChat admin home"
      className={cn(
        "focus-visible:ring-sidebar-ring flex h-9 cursor-pointer items-center gap-3 overflow-hidden rounded-[10px] no-underline outline-none focus-visible:ring-2",
        collapsed ? "size-8 justify-center gap-0" : "w-full",
      )}
    >
      <span className="bg-ember flex size-7 shrink-0 items-center justify-center rounded-[8px] text-[10px] font-extrabold tracking-[-0.08em] text-white shadow-[0_4px_14px_rgba(196,85,22,0.32)]">
        Support
      </span>
      {!collapsed ? (
        <span className="min-w-0 truncate text-sm font-extrabold tracking-[-0.02em] text-white">
          SupportChat
        </span>
      ) : null}
    </Link>
  </SidebarHeader>
)

const AdminSidebarFooter = ({
  collapsed,
  displayName,
  pathname,
}: {
  collapsed: boolean
  displayName: string
  pathname: string
}) => (
  <SidebarFooter className={cn("gap-2 p-3", collapsed && "items-center px-0 py-2")}>
    <div
      className={cn(
        "flex items-center gap-1",
        collapsed ? "flex-col" : "w-full justify-between px-0.5",
      )}
    >
      <ThemeToggle compact />
      <SidebarTrigger className="text-white/70 hover:bg-white/10 hover:text-white" />
    </div>
    <SidebarMenu className={cn("w-full", collapsed && "w-auto items-center")}>
      <AdminSidebarAccount displayName={displayName} pathname={pathname} collapsed={collapsed} />
    </SidebarMenu>
  </SidebarFooter>
)

const AdminSidebar = ({ displayName }: { displayName: string }) => {
  const pathname = usePathname()
  const { state } = useSidebar()
  const collapsed = state === "collapsed"

  return (
    <Sidebar
      data-testid="admin-sidebar"
      collapsible="icon"
      className="bg-sidebar border-r-0! border-transparent"
      style={adminSidebarStyle}
    >
      <AdminSidebarBrand collapsed={collapsed} />
      <SidebarContent>
        <SidebarGroup className={cn("px-3 pt-4 pb-2", collapsed && "items-center p-0 py-2")}>
          <SidebarGroupContent className={cn(collapsed && "flex justify-center")}>
            <AdminSidebarLinks links={workspaceLinks} pathname={pathname} collapsed={collapsed} />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <AdminSidebarFooter collapsed={collapsed} displayName={displayName} pathname={pathname} />
    </Sidebar>
  )
}

export const AdminShell = ({ children }: { children: ReactNode }) => {
  const router = useRouter()
  const { sidebarOpen, setSidebarOpen } = usePreferences()
  const [user, setUser] = useState<StaffUser | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)

  useEffect(() => {
    let active = true
    const boot = async () => {
      const nextUser = await refreshSession()
      if (!active) {
        return
      }
      if (nextUser === null) {
        router.replace("/login")
        return
      }
      setUser(nextUser)
      setCheckingSession(false)
    }
    void boot()
    return () => {
      active = false
    }
  }, [router])

  const frame = user === null ? <StaffPageSkeleton /> : children

  return (
    <>
      <ClientErrorReporter />
      <SidebarProvider
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
        style={{ "--sidebar-width": "15rem", "--sidebar-width-icon": "3rem" } as CSSProperties}
      >
        <AdminSidebar displayName={user?.display_name ?? "Loading workspace"} />
        <SidebarInset className="flex h-svh min-h-0 min-w-0 flex-col overflow-hidden bg-[#14161b] p-2">
          <AdminUserContext.Provider value={user}>
            <div className="bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl">
              {checkingSession ? <StaffPageSkeleton /> : frame}
            </div>
          </AdminUserContext.Provider>
        </SidebarInset>
      </SidebarProvider>
    </>
  )
}
