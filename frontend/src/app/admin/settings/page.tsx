"use client"

import { SettingsConsole } from "@/app/settings/settings-console"
import { useAdminUser } from "@/components/admin/admin-shell"

export default function AdminSettingsPage() {
  const user = useAdminUser()
  return (
    <SettingsConsole displayName={user.display_name} email={user.email} isAdmin={user.is_admin} />
  )
}
