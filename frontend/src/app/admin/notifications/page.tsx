import type { Metadata } from "next"

import { StaffHeader } from "@/components/admin/staff-nav"
import { NotificationPreferences } from "@/components/notifications/notification-preferences"

export const metadata: Metadata = {
  title: "Notification settings",
}

export default function NotificationSettingsPage() {
  return (
    <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col">
      <StaffHeader
        title="Notification settings"
        description="Choose which chat activity reaches you, and how you hear about it."
      />
      <div id="main-content" className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
          <NotificationPreferences />
        </div>
      </div>
    </div>
  )
}
