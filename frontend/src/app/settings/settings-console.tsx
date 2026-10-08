"use client"

import { Bell, ChevronRight } from "lucide-react"
import Link from "next/link"

import { SignOutButton } from "@/components/admin/sign-out-button"
import { StaffHeader } from "@/components/admin/staff-nav"
import { Button } from "@/components/ui/button"

type SettingsConsoleProps = {
  displayName: string
  email: string
  isAdmin: boolean
}

const notificationSettingsLink = <Link href="/admin/notifications" />

export const SettingsConsole = ({ displayName, email, isAdmin }: SettingsConsoleProps) => {
  return (
    <div className="view-transition-enter bg-ice flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <StaffHeader title="Settings" description="Your specialist profile for this workspace." />
        <div
          id="main-content"
          className="mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col gap-5 overflow-y-auto px-4 py-4 sm:px-5 sm:py-6 lg:px-8 lg:py-8 [&>section]:shrink-0"
        >
          <ProfileCard displayName={displayName} email={email} isAdmin={isAdmin} />
          <Button
            variant="outline"
            className="h-auto min-h-14 justify-start gap-3 px-4 py-3 whitespace-normal"
            render={notificationSettingsLink}
          >
            <Bell aria-hidden="true" className="text-steel size-5" />
            <span className="flex-1 text-left">Notification settings</span>
            <ChevronRight aria-hidden="true" className="text-mute size-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

const ProfileCard = ({
  displayName,
  email,
  isAdmin,
}: {
  displayName: string
  email: string
  isAdmin: boolean
}) => (
  <section className="border-line bg-paper rounded-lg border p-5 lg:p-6">
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
          Specialist profile
        </p>
        <h2 className="text-navy heading mt-1 text-base">Your account</h2>
      </div>
      <div className="flex items-center gap-2">
        <span className="bg-ice-2 text-steel rounded-lg px-3 py-1 text-[10px] font-bold uppercase">
          {isAdmin ? "Admin" : "Specialist"}
        </span>
        <SignOutButton className="text-navy hover:bg-ice-2" />
      </div>
    </div>
    <dl className="grid gap-4 sm:grid-cols-2">
      <div>
        <dt className="text-mute text-xs font-medium">Display name</dt>
        <dd className="text-ink mt-1 text-sm">{displayName}</dd>
      </div>
      <div>
        <dt className="text-mute text-xs font-medium">Work email</dt>
        <dd className="text-ink mt-1 text-sm">{email}</dd>
      </div>
    </dl>
    <p className="text-mute mt-4 text-xs">Profile changes are managed by an administrator.</p>
  </section>
)
