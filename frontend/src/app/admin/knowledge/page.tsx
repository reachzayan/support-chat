"use client"

import { KnowledgeConsole } from "@/app/knowledge/knowledge-console"
import { useAdminUser } from "@/components/admin/admin-shell"

export default function AdminKnowledgePage() {
  const user = useAdminUser()
  return <KnowledgeConsole isAdmin={user.is_admin} displayName={user.display_name} />
}
