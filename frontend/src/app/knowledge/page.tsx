"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { fetchMe, refreshSession, type StaffUser } from "@/lib/auth-client"

import { KnowledgeConsole } from "./knowledge-console"

export default function KnowledgePage() {
  const router = useRouter()
  const [user, setUser] = useState<StaffUser | null>(null)

  useEffect(() => {
    const boot = async () => {
      const refreshed = await refreshSession()
      const me = refreshed ?? (await fetchMe())
      if (me === null) {
        router.replace("/login")
        return
      }
      setUser(me)
    }
    void boot()
  }, [router])

  if (user === null) {
    return null
  }
  return <KnowledgeConsole isAdmin={user.is_admin} displayName={user.display_name} />
}
