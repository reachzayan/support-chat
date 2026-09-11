"use client"

import { LogsConsole } from "@/app/logs/logs-console"
import { useAdminUser } from "@/components/admin/admin-shell"

export default function AdminLogsPage() {
  const user = useAdminUser()
  return <LogsConsole isAdmin={user.is_admin} displayName={user.display_name} />
}
