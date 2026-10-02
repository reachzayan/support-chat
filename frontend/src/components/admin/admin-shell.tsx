/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-object-as-prop */

"use client"

import { cn } from "cn"
import {
  Activity,
  Ban,
  BookOpen,
  ChevronDown,
  Globe2,
  Inbox,
  Lightbulb,
  MessageSquareText,
  ScrollText,
  Table2,
  type LucideIcon,
} from "lucide-react"
import { motion } from "motion/react"
import Link from "next/link"
import { usePathname } from "next/navigation"
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
import { SignOutButton } from "@/components/admin/sign-out-button"
import { BrandMark } from "@/components/brand-mark"
import { usePreferences } from "@/components/preferences-context"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
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
import {
  redirectToLogin,
  refreshSession,
  type RefreshSessionResult,
  type StaffUser,
} from "@/lib/auth-client"

const MotionLink = motion.create(Link)

const AdminUserContext = createContext<StaffUser | null>(null)

export const useAdminUser = () => {
  const user = useContext(AdminUserContext)
  if (user === null) {
    throw new Error("useAdminUser must be used within AdminShell.")
  }
  return user
}

export const useOptionalAdminUser = () => useContext(AdminUserContext)

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
  { href: "/admin/suggested-faqs", label: "Suggested FAQs", icon: Lightbulb },
  { href: "/admin/blocked", label: "Blocked", icon: Ban },
  { href: "/admin/sites", label: "Sites", icon: Globe2 },
  { href: "/admin/status", label: "Status", icon: Activity },
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

const NAV_SPRING = {
  type: "spring",
  stiffness: 500,
  damping: 42,
  mass: 0.6,
} as const

const AvatarMark = ({ initials }: { initials: string }) => (
  <span className="relative flex size-7 shrink-0 items-center justify-center">
    <span className="bg-sidebar-accent flex size-7 items-center justify-center rounded-[8px] text-[10px] leading-none font-bold text-white">
      {initials}
    </span>
    <span
      aria-hidden="true"
      className="border-sidebar bg-steel absolute -right-0.5 -bottom-0.5 size-2 rounded-full border-2"
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
          whileTap={{ scale: 0.96 }}
          className="cursor-pointer no-underline"
        />
      }
      className={cn(
        "text-sidebar-foreground/60 data-active:text-sidebar-foreground relative isolate h-11 rounded-lg px-3 text-sm font-semibold no-underline transition-[width,height,padding,colors] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-white/4.5 hover:text-sidebar-foreground/90 data-active:hover:bg-transparent",
        collapsed && "size-8! justify-center gap-0 p-0!",
      )}
    >
      {active ? (
        <motion.span
          layoutId="admin-nav-active"
          transition={NAV_SPRING}
          aria-hidden="true"
          className={cn(
            "absolute inset-0 -z-10 rounded-lg",
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
  isAdmin,
  pathname,
  collapsed,
}: {
  displayName: string
  isAdmin: boolean
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
                  "flex size-8 items-center justify-center rounded-lg no-underline outline-none transition-colors hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-steel",
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
        className="text-sidebar-foreground rounded-lg px-2 no-underline hover:bg-white/5"
      >
        <AvatarMark initials={initials} />
        <span className="grid min-w-0 flex-1 text-left text-xs">
          <span className="heading truncate text-sm text-white">{displayName}</span>
          <span className="truncate text-[10px] text-white/50">
            {isAdmin ? "Admin" : "Specialist"}
          </span>
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
  "--sidebar-ring": "#2456A0",
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
        "focus-visible:ring-sidebar-ring flex h-9 cursor-pointer items-center gap-3 overflow-hidden rounded-lg no-underline outline-none focus-visible:ring-2",
        collapsed ? "size-8 justify-center gap-0" : "w-full",
      )}
    >
      <BrandMark size={28} className="size-7" />
      {!collapsed ? (
        <span className="heading min-w-0 truncate text-sm text-white">SupportChat</span>
      ) : null}
    </Link>
  </SidebarHeader>
)

const AdminSidebarFooter = ({
  collapsed,
  displayName,
  isAdmin,
  pathname,
}: {
  collapsed: boolean
  displayName: string
  isAdmin: boolean
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
    <SignOutButton
      iconOnly={collapsed}
      className={cn(
        "text-white/70 hover:bg-white/10 hover:text-white",
        collapsed ? "size-8 justify-center" : "w-full justify-start",
      )}
    />
    <SidebarMenu className={cn("w-full", collapsed && "w-auto items-center")}>
      <AdminSidebarAccount
        displayName={displayName}
        isAdmin={isAdmin}
        pathname={pathname}
        collapsed={collapsed}
      />
    </SidebarMenu>
  </SidebarFooter>
)

const AdminSidebar = ({ displayName, isAdmin }: { displayName: string; isAdmin: boolean }) => {
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
      <AdminSidebarFooter
        collapsed={collapsed}
        displayName={displayName}
        isAdmin={isAdmin}
        pathname={pathname}
      />
    </Sidebar>
  )
}

const useAdminSession = () => {
  const [user, setUser] = useState<StaffUser | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)
  const [sessionError, setSessionError] = useState(false)

  useEffect(() => {
    let active = true
    const apply = (result: RefreshSessionResult) => {
      if (result.status === "unauthenticated") {
        setUser(null)
        redirectToLogin()
        return
      }
      if (result.status === "unavailable") {
        setSessionError(true)
        setCheckingSession(false)
        return
      }
      setSessionError(false)
      setUser(result.user)
      setCheckingSession(false)
    }
    const boot = async () => {
      const result = await refreshSession()
      if (!active) {
        return
      }
      apply(result)
    }
    void boot()
    const handlePageShow = (event: Event) => {
      if (!("persisted" in event) || !(event as PageTransitionEvent).persisted) {
        return
      }
      void boot()
    }
    window.addEventListener("pageshow", handlePageShow)
    return () => {
      active = false
      window.removeEventListener("pageshow", handlePageShow)
    }
  }, [])

  const handleRetry = () => {
    setSessionError(false)
    setCheckingSession(true)
    void (async () => {
      const result = await refreshSession()
      if (result.status === "unauthenticated") {
        setUser(null)
        redirectToLogin()
        return
      }
      if (result.status === "unavailable") {
        setSessionError(true)
        setCheckingSession(false)
        return
      }
      setSessionError(false)
      setUser(result.user)
      setCheckingSession(false)
    })()
  }

  return { user, checkingSession, sessionError, handleRetry }
}

export const AdminShell = ({ children }: { children: ReactNode }) => {
  const { sidebarOpen, setSidebarOpen } = usePreferences()
  const { user, checkingSession, sessionError, handleRetry } = useAdminSession()

  const frame = sessionError ? (
    <SessionRetryPanel onRetry={handleRetry} />
  ) : user === null ? (
    <StaffPageSkeleton />
  ) : (
    children
  )

  return (
    <>
      <ClientErrorReporter />
      <SidebarProvider
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
        style={
          {
            "--sidebar-width": "15rem",
            "--sidebar-width-icon": "3rem",
          } as CSSProperties
        }
      >
        <AdminSidebar
          displayName={user?.display_name ?? "Loading workspace"}
          isAdmin={user?.is_admin ?? false}
        />
        <SidebarInset className="flex h-svh min-h-0 min-w-0 flex-col overflow-hidden overscroll-none bg-[#14161b] p-2">
          <AdminUserContext.Provider value={user}>
            <div className="bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden overscroll-none rounded-lg">
              {checkingSession ? <StaffPageSkeleton /> : frame}
            </div>
          </AdminUserContext.Provider>
        </SidebarInset>
      </SidebarProvider>
    </>
  )
}

const SessionRetryPanel = ({ onRetry }: { onRetry: () => void }) => (
  <div className="bg-ice flex min-h-0 flex-1 flex-col items-center justify-center px-6 text-center">
    <p className="text-navy heading text-sm">Could not reach the staff API.</p>
    <p className="text-mute mt-2 text-sm">Check your connection and try again.</p>
    <Button
      type="button"
      variant="default"
      size="lg"
      className="mt-4 font-semibold"
      onClick={onRetry}
    >
      Retry
    </Button>
  </div>
)
