"use client"

import { SitesConsole } from "@/app/sites/sites-console"
import { useAdminUser } from "@/components/admin/admin-shell"

export default function AdminSitesPage() {
  const user = useAdminUser()
  return <SitesConsole isAdmin={user.is_admin} displayName={user.display_name} />
}
