/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-object-as-prop */

"use client"

import { cn } from "cn"
import { ChevronDown } from "lucide-react"
import { motion } from "motion/react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  createContext,
  useCallback,
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
import { NotificationBell } from "@/components/notifications/notification-bell"
import {
  NotificationsProvider,
  useNotificationState,
} from "@/components/notifications/notifications-context"
import { UnreadBadge } from "@/components/notifications/unread-badge"
import { usePreferences } from "@/components/preferences-context"
import { WorkspaceSearch } from "@/components/search/workspace-search"
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
import { StateIcon, type StateIconName } from "@/components/ui/state-icon"
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
  icon: StateIconName
}

const navigationGroups: { label: string; links: AdminLink[] }[] = [
  {
    label: "Conversations",
    links: [
      { href: "/admin/inbox", label: "Inbox", icon: "tray" },
      { href: "/admin/data", label: "Data", icon: "table" },
      { href: "/admin/blocked", label: "Blocked", icon: "prohibit" },
    ],
  },
  {
    label: "Knowledge",
    links: [
      { href: "/admin/knowledge", label: "Knowledge base", icon: "book-open" },
      { href: "/admin/canned-responses", label: "Canned responses", icon: "chat-text" },
      { href: "/admin/suggested-faqs", label: "Suggested FAQs", icon: "lightbulb" },
    ],
  },
  {
    label: "Administration",
    links: [
      { href: "/admin/sites", label: "Sites", icon: "globe" },
      { href: "/admin/status", label: "Status", icon: "pulse" },
      { href: "/admin/logs", label: "Logs", icon: "scroll" },
    ],
  },
  {
    label: "Preferences",
    links: [{ href: "/admin/notifications", label: "Notification settings", icon: "bell" }],
  },
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

const useInboxNav = (href: string, label: string) => {
  const { feed } = useNotificationState()
  const count = href === "/admin/inbox" ? (feed?.unread_count ?? 0) : 0
  return { count, accessibleLabel: count > 0 ? `${label}, ${count} unread` : label }
}

const AdminSidebarLink = ({
  href,
  label,
  icon,
  active,
  collapsed,
}: AdminLink & { active: boolean; collapsed: boolean }) => {
  const { count, accessibleLabel } = useInboxNav(href, label)
  return (
    <SidebarMenuItem className={cn("flex w-full", collapsed && "justify-center")}>
      <SidebarMenuButton
        isActive={active}
        tooltip={label}
        render={
          <MotionLink
            href={href}
            aria-label={accessibleLabel}
            aria-current={active ? "page" : undefined}
            whileTap={{ scale: 0.96 }}
            className="cursor-pointer no-underline"
          />
        }
        className={cn(
          "text-sidebar-foreground/60 data-active:text-sidebar-foreground relative isolate h-11 overflow-visible rounded-lg px-3 text-sm font-semibold no-underline transition-[width,height,padding,colors] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-white/4.5 hover:text-sidebar-foreground/90 data-active:hover:bg-transparent",
          collapsed && "size-8! justify-center gap-0 p-0! hover:bg-transparent!",
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
        <StateIcon name={icon} className="size-4.5" />
        {!collapsed ? <span className="min-w-0 truncate">{label}</span> : null}
        <UnreadBadge
          count={count}
          className={collapsed ? "ring-sidebar absolute -top-1 -right-1 ring-2" : "ml-auto"}
        />
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

const AdminSidebarLinks = ({
  links,
  pathname,
  collapsed,
  category,
}: {
  links: AdminLink[]
  pathname: string
  collapsed: boolean
  category: string
}) => (
  <SidebarMenu aria-label={category} className={cn("w-full gap-1", collapsed && "items-center")}>
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
                aria-current={active ? "page" : undefined}
                data-active={active || undefined}
                className={cn(
                  "flex size-8 items-center justify-center rounded-lg no-underline outline-none transition-colors hover:text-white focus-visible:ring-2 focus-visible:ring-steel",
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
        render={
          <Link
            href="/admin/settings"
            aria-label={accountLabel}
            aria-current={active ? "page" : undefined}
          />
        }
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
      "flex h-(--workspace-toolbar-height) shrink-0 flex-col justify-center px-3",
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
      <BrandMark size={32} className="size-8" />
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
    <div className={cn("flex items-center", collapsed ? "justify-center" : "w-full")}>
      {collapsed ? (
        <ThemeToggle compact className="size-11 md:size-7" />
      ) : (
        <ThemeToggle showLabel className="w-full" />
      )}
    </div>
    <SignOutButton
      iconOnly={collapsed}
      className={cn(
        "text-white/70 hover:text-white",
        collapsed ? "size-8 justify-center" : "min-h-11 w-full justify-start md:min-h-8",
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
  const { state, isMobile, setOpenMobile } = useSidebar()
  const collapsed = !isMobile && state === "collapsed"
  const closeOnNavigate = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (isMobile && event.target instanceof Element && event.target.closest("a[href]")) {
        setOpenMobile(false)
      }
    },
    [isMobile, setOpenMobile],
  )

  return (
    <Sidebar
      data-testid="admin-sidebar"
      collapsible="icon"
      className="bg-sidebar border-r-0! border-transparent"
      style={adminSidebarStyle}
      onClickCapture={closeOnNavigate}
    >
      <AdminSidebarBrand collapsed={collapsed} />
      <SidebarContent>
        {navigationGroups.map((group) => (
          <SidebarGroup
            key={group.label}
            className={cn("px-3 pt-4 pb-1", collapsed && "items-center px-0 pt-3 pb-1")}
          >
            <span
              aria-hidden="true"
              className={cn(
                "mb-1.5 px-3 text-[10px] font-medium tracking-wider text-sidebar-foreground/50",
                collapsed && "sr-only",
              )}
            >
              {group.label}
            </span>
            <SidebarGroupContent className={cn(collapsed && "flex justify-center")}>
              <AdminSidebarLinks
                links={group.links}
                pathname={pathname}
                collapsed={collapsed}
                category={group.label}
              />
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
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
        <AuthenticatedNotifications user={user}>
          <AdminSidebar
            displayName={user?.display_name ?? "Loading workspace"}
            isAdmin={user?.is_admin ?? false}
          />
          <SidebarInset className="isolate flex h-dvh min-h-0 min-w-0 flex-col overflow-hidden overscroll-none bg-[#14161b] p-0 md:px-2 md:pb-2">
            <AdminUserContext.Provider value={user}>
              <WorkspaceToolbar userId={user?.id} />
              <div className="bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden overscroll-none md:rounded-lg">
                {checkingSession ? <StaffPageSkeleton /> : frame}
              </div>
            </AdminUserContext.Provider>
          </SidebarInset>
        </AuthenticatedNotifications>
      </SidebarProvider>
    </>
  )
}

const AuthenticatedNotifications = ({
  user,
  children,
}: {
  user: StaffUser | null
  children: ReactNode
}) => (
  <NotificationsProvider key={user?.id ?? "signed-out"} enabled={user !== null}>
    {children}
  </NotificationsProvider>
)

const WorkspaceToolbar = ({ userId }: { userId: string | undefined }) => {
  const { isMobile, openMobile, toggleSidebar } = useSidebar()
  const user = useOptionalAdminUser()
  return (
    <header className="grid h-(--workspace-toolbar-height) shrink-0 grid-cols-[2.75rem_minmax(0,1fr)_2.75rem] items-center gap-2 text-white">
      {isMobile ? (
        <Button
          variant="ghost"
          size="icon"
          aria-label={openMobile ? "Close navigation" : "Open navigation"}
          aria-expanded={openMobile}
          className="size-11 text-white hover:text-white aria-expanded:text-white"
          onClick={toggleSidebar}
        >
          <StateIcon name="list" className="size-5" />
        </Button>
      ) : (
        <SidebarTrigger className="size-11 text-white/85 hover:text-white aria-expanded:text-white" />
      )}
      {userId ? (
        <div className="w-full max-w-2xl min-w-0 justify-self-center">
          <WorkspaceSearch isAdmin={user?.is_admin ?? false} />
        </div>
      ) : (
        <span className="heading flex-1 px-2 text-sm">SupportChat</span>
      )}
      {userId ? <NotificationBell key={userId} /> : null}
    </header>
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
