/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-object-as-prop */

"use client"

import {
  BookOpen,
  ChevronDown,
  Globe2,
  Inbox,
  ScrollText,
  Settings2,
  Table2,
  type LucideIcon,
} from "lucide-react"
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
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { refreshSession, type StaffUser } from "@/lib/auth-client"

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
  { href: "/admin/sites", label: "Sites", icon: Globe2 },
  { href: "/admin/logs", label: "Logs", icon: ScrollText },
]

const accountLinks: AdminLink[] = [{ href: "/admin/settings", label: "Settings", icon: Settings2 }]

const initialsFor = (displayName: string) =>
  displayName
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase() || "SP"

const AdminSidebarLinks = ({ links, pathname }: { links: AdminLink[]; pathname: string }) => (
  <SidebarMenu className="gap-1.5 group-data-[collapsible=icon]:items-center">
    {links.map(({ href, label, icon: Icon }) => (
      <SidebarMenuItem
        key={href}
        className="group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:justify-center"
      >
        <SidebarMenuButton
          isActive={pathname === href || pathname.startsWith(`${href}/`)}
          tooltip={label}
          render={<Link href={href} aria-label={label} className="cursor-pointer" />}
          className="hover:bg-sidebar-accent data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:before:bg-ember relative h-10 rounded-md px-3 text-sm font-semibold group-data-[collapsible=icon]:mx-auto data-active:before:absolute data-active:before:top-2 data-active:before:bottom-2 data-active:before:left-0 data-active:before:w-0.5"
        >
          <Icon aria-hidden="true" className="size-[18px]" strokeWidth={1.8} />
          <span>{label}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    ))}
  </SidebarMenu>
)

const AdminSidebar = ({ displayName }: { displayName: string }) => {
  const pathname = usePathname()

  return (
    <Sidebar
      data-testid="admin-sidebar"
      collapsible="icon"
      variant="sidebar"
      className="border-sidebar-border bg-sidebar"
    >
      <SidebarHeader className="border-sidebar-border border-b px-3 py-4">
        <Link
          href="/admin/inbox"
          aria-label="SupportChat admin home"
          className="group focus-visible:ring-sidebar-ring flex h-10 cursor-pointer items-center gap-3 overflow-hidden rounded-md px-1 outline-none focus-visible:ring-2"
        >
          <span className="bg-ember text-paper flex size-9 shrink-0 items-center justify-center rounded-md text-[11px] font-extrabold tracking-[-0.08em]">
            Support
          </span>
          <span className="min-w-0 group-data-[collapsible=icon]:hidden">
            <span className="text-navy block truncate text-sm font-extrabold tracking-[-0.02em]">
              SupportChat
            </span>
          </span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup className="px-3 pt-4 pb-2 group-data-[collapsible=icon]:px-2 group-data-[collapsible=icon]:py-3">
          <SidebarGroupLabel className="text-mute px-3 text-[10px] font-bold tracking-[0.14em] uppercase">
            Workspace
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <AdminSidebarLinks links={workspaceLinks} pathname={pathname} />
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarSeparator />
        <SidebarGroup className="px-3 py-2 group-data-[collapsible=icon]:px-2 group-data-[collapsible=icon]:py-3">
          <SidebarGroupLabel className="text-mute px-3 text-[10px] font-bold tracking-[0.14em] uppercase">
            Account
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <AdminSidebarLinks links={accountLinks} pathname={pathname} />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-sidebar-border border-t p-3">
        <SidebarMenu className="group-data-[collapsible=icon]:items-center">
          <SidebarMenuItem className="group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:justify-center">
            <SidebarMenuButton
              size="lg"
              tooltip={displayName}
              render={<button type="button" aria-label={`${displayName} account`} />}
              className="hover:bg-sidebar-accent rounded-md px-2 group-data-[collapsible=icon]:mx-auto"
            >
              <span className="bg-ice-2 text-steel flex size-8 shrink-0 items-center justify-center rounded-md text-[10px] font-bold">
                {initialsFor(displayName)}
              </span>
              <span className="grid min-w-0 flex-1 text-left text-xs group-data-[collapsible=icon]:hidden">
                <span className="text-navy truncate font-bold">{displayName}</span>
                <span className="text-mute truncate text-[10px]">Available now</span>
              </span>
              <ChevronDown
                aria-hidden="true"
                className="ml-auto size-4 group-data-[collapsible=icon]:hidden"
              />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

const LoadingContent = () => (
  <div className="flex flex-1 flex-col gap-6 p-5 lg:p-8" aria-label="Loading admin workspace">
    <div className="flex items-center gap-3">
      <span className="bg-line size-9 animate-pulse rounded-md" />
      <span className="bg-line h-5 w-28 animate-pulse rounded-md" />
    </div>
    <div className="bg-paper border-line flex-1 rounded-md border" />
  </div>
)

export const AdminShell = ({ children }: { children: ReactNode }) => {
  const router = useRouter()
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

  const frame = user === null ? <LoadingContent /> : children

  return (
    <>
      <ClientErrorReporter />
      <SidebarProvider
        defaultOpen
        style={{ "--sidebar-width": "16rem", "--sidebar-width-icon": "4rem" } as CSSProperties}
      >
        <AdminSidebar displayName={user?.display_name ?? "Loading workspace"} />
        <SidebarInset className="bg-ice flex h-svh min-h-0 min-w-0 flex-col overflow-hidden">
          <div className="border-line bg-paper flex h-11 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger className="-ml-1" />
            <span className="bg-line mx-1 h-4 w-px" />
            <span className="text-navy text-xs font-extrabold">SupportChat</span>
            <span className="text-mute ml-auto hidden text-[10px] font-medium tracking-[0.12em] uppercase md:inline">
              Ctrl / ⌘ B
            </span>
          </div>
          <AdminUserContext.Provider value={user}>
            <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
              {checkingSession ? <LoadingContent /> : frame}
            </div>
          </AdminUserContext.Provider>
        </SidebarInset>
      </SidebarProvider>
    </>
  )
}
