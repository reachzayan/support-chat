"use client"

import { useAdminUser } from "@/components/admin/admin-shell"
import { InboxConsole } from "@/components/inbox/inbox-console"

export default function AdminInboxPage() {
  return <InboxConsole user={useAdminUser()} />
}
