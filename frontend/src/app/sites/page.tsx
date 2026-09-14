"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { StaffPageSkeleton } from "@/components/admin/loading-skeleton"
import { fetchMe, refreshSession, type StaffUser } from "@/lib/auth-client"

import { SitesConsole } from "./sites-console"

export default function SitesPage() {
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
    return <StaffPageSkeleton />
  }
  return <SitesConsole isAdmin={user.is_admin} displayName={user.display_name} />
}
