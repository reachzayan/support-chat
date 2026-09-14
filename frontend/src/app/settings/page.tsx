"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { StaffPageSkeleton } from "@/components/admin/loading-skeleton"
import { fetchMe, refreshSession, type StaffUser } from "@/lib/auth-client"

import { SettingsConsole } from "./settings-console"

export default function SettingsPage() {
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

  return (
    <SettingsConsole displayName={user.display_name} email={user.email} isAdmin={user.is_admin} />
  )
}
