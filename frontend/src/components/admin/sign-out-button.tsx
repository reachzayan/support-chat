"use client"

import { useCallback, useState } from "react"

import { Button } from "@/components/ui/button"
import { StateIcon } from "@/components/ui/state-icon"
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
        <StateIcon name="power" className="size-4" />
      ) : pending ? (
        "Signing out…"
      ) : (
        "Sign out"
      )}
    </Button>
  )
}
