"use client"

import { Power } from "lucide-react"
import { useCallback, useState } from "react"

import { Button } from "@/components/ui/button"
import { logout, redirectToLogin } from "@/lib/auth-client"

export const SignOutButton = ({
  className,
  iconOnly = false,
}: {
  className?: string
  iconOnly?: boolean
}) => {
  const [pending, setPending] = useState(false)
  const handleSignOut = useCallback(async () => {
    setPending(true)
    await logout()
    redirectToLogin()
  }, [])
  return (
    <Button
      type="button"
      variant="ghost"
      size={iconOnly ? "icon" : "sm"}
      onClick={handleSignOut}
      disabled={pending}
      aria-label="Sign out"
      className={className}
    >
      {iconOnly ? (
        <Power aria-hidden="true" className="size-4" strokeWidth={1.8} />
      ) : pending ? (
        "Signing out…"
      ) : (
        "Sign out"
      )}
    </Button>
  )
}
