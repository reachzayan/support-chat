"use client"

import { useRouter } from "next/navigation"
import { useCallback } from "react"

import { LoginForm } from "./login-form"
import { LoginStage } from "./login-stage"

export default function LoginPage() {
  const router = useRouter()
  const handleSuccess = useCallback(() => {
    router.push("/admin/inbox")
  }, [router])

  return (
    <LoginStage>
      <LoginForm onSuccess={handleSuccess} />
    </LoginStage>
  )
}
