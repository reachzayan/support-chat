"use client"

import { usePathname } from "next/navigation"
import { useEffect } from "react"

import { refreshSession } from "@/lib/auth-client"

export const StaffSessionBootstrap = () => {
  const pathname = usePathname()
  useEffect(() => {
    if (pathname === "/widget" || pathname.startsWith("/widget/")) {
      return
    }
    void refreshSession()
  }, [pathname])
  return null
}
