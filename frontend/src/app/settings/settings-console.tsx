"use client"

import { StaffHeader } from "@/components/admin/staff-nav"
import { Input } from "@/components/ui/input"

type SettingsConsoleProps = {
  displayName: string
  email: string
  isAdmin: boolean
}

export const SettingsConsole = ({ displayName, email, isAdmin }: SettingsConsoleProps) => {
  return (
    <div className="view-transition-enter bg-ice flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <StaffHeader
          title="Settings"
          description="Manage your specialist profile and workspace details."
        />
        <div
          id="main-content"
          className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-5 py-6 lg:px-8 lg:py-8"
        >
          <ProfileCard displayName={displayName} email={email} isAdmin={isAdmin} />
          <WorkspaceCard />
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
  <section className="border-line bg-paper rounded-[8px] border p-5 lg:p-6">
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
          Specialist profile
        </p>
        <h2 className="text-navy heading mt-1 text-base">Your account</h2>
      </div>
      <span className="bg-ice-2 text-steel rounded-full px-3 py-1 text-[10px] font-bold uppercase">
        {isAdmin ? "Admin" : "Specialist"}
      </span>
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      <ProfileField id="settings-name" label="Display name" value={displayName} />
      <ProfileField id="settings-email" label="Work email" value={email} />
    </div>
    <p className="text-mute mt-4 text-xs">Profile changes are managed by an administrator.</p>
  </section>
)

const ProfileField = ({ id, label, value }: { id: string; label: string; value: string }) => (
  <label className="text-ink flex flex-col gap-1 text-xs font-medium" htmlFor={id}>
    {label}
    <Input
      id={id}
      readOnly
      value={value}
      className="border-line bg-ice text-ink mt-1 min-h-11 rounded-[8px] border px-3 text-sm font-normal outline-none"
    />
  </label>
)

const WorkspaceCard = () => (
  <section className="border-line bg-navy dark:text-navy-deep rounded-[8px] border border-transparent p-5 text-white lg:p-6">
    <p className="dark:text-navy-deep/55 text-[11px] font-semibold tracking-[0.2em] text-white/55 uppercase">
      Workspace
    </p>
    <div className="mt-2 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <h2 className="heading text-lg">SampleSite operations</h2>
        <p className="dark:text-navy-deep/65 mt-1 max-w-md text-xs leading-5 text-white/65">
          Your inbox, ingested knowledge, and site configuration live in this workspace.
        </p>
      </div>
      <span className="dark:text-navy-deep/45 font-mono text-xs text-white/45">
        supportchat / samplesite
      </span>
    </div>
  </section>
)
