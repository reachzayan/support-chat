"use client"

import { useSearchParams } from "next/navigation"
import { Suspense } from "react"

import { useAdminUser } from "@/components/admin/admin-shell"
import { InboxConsole } from "@/components/inbox/inbox-console"

const InboxPageContent = () => {
  const conversationId = useSearchParams().get("conversation")
  return <InboxConsole user={useAdminUser()} initialConversationId={conversationId} />
}

export default function AdminInboxPage() {
  return (
    <Suspense>
      <InboxPageContent />
    </Suspense>
  )
}
