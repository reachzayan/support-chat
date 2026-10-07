import type { Metadata } from "next"
import type { ReactNode } from "react"

import { AdminShell } from "@/components/admin/admin-shell"
import { WorkspaceRoute } from "@/components/search/workspace-route"

export const metadata: Metadata = {
  title: "Admin",
}

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminShell>
      <WorkspaceRoute>{children}</WorkspaceRoute>
    </AdminShell>
  )
}
