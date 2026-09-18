"use client"

import { Effect, Exit } from "effect"
import { useCallback, useState, type ChangeEvent, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { FieldError } from "@/components/ui/field"
import { login } from "@/lib/auth-client"
import { parseStaffEmail } from "@/lib/staff-email"
import { emailError, requiredError } from "@/lib/validation"

import { LoginFields } from "./login-fields"

const GENERIC_ERROR = "Invalid email or password"

const updateLoginError = (
  setFieldErrors: (updater: (current: Record<string, string>) => Record<string, string>) => void,
  key: string,
  error: string | null,
) => {
  setFieldErrors((current) => {
    if (error) return { ...current, [key]: error }
    const next = { ...current }
    delete next[key]
    return next
  })
}

const visibleLoginErrors = (email: string, password: string) => {
  const parsed = Effect.runSyncExit(parseStaffEmail(email))
  const nextErrors = {
    email: Exit.isFailure(parsed) ? emailError(email) : null,
    password: requiredError("Password", password),
  }
  return Object.fromEntries(
    Object.entries(nextErrors).filter((entry): entry is [string, string] => entry[1] !== null),
  )
}

export const LoginForm = ({ onSuccess }: { onSuccess: () => void }) => {
  const form = useLoginForm(onSuccess)

  return (
    <form
      method="post"
      action="/login"
      onSubmit={form.handleSubmit}
      className="border-line/80 bg-paper w-full rounded-[28px] border px-7 py-8 shadow-[0_24px_60px_rgba(13,31,58,0.10)] sm:px-9 sm:py-9"
    >
      <h1 className="text-navy heading text-[1.65rem]">Sign in</h1>
      <p className="text-mute mt-1.5 mb-7 text-sm">Invited specialists only.</p>
      <LoginFields
        email={form.email}
        password={form.password}
        showPassword={form.showPassword}
        fieldErrors={form.fieldErrors}
        onEmailChange={form.handleEmailChange}
        onPasswordChange={form.handlePasswordChange}
        onEmailBlur={form.handleEmailBlur}
        onPasswordBlur={form.handlePasswordBlur}
        onTogglePassword={form.handleTogglePassword}
      />
      <div className="flex flex-col gap-3">
        <FieldError>{form.error ?? undefined}</FieldError>
        <Button
          type="submit"
          disabled={form.pending}
          aria-busy={form.pending}
          className="bg-ember hover:bg-ember-mid disabled:bg-ember-soft dark:text-navy-deep h-12 rounded-2xl px-4 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(196,85,22,0.28)]"
        >
          Sign in
        </Button>
      </div>
    </form>
  )
}

const useLoginForm = (onSuccess: () => void) => {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const handleEmailChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value)
  }, [])
  const handlePasswordChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setPassword(event.target.value)
  }, [])
  const handleEmailBlur = useCallback(() => {
    updateLoginError(setFieldErrors, "email", emailError(email))
  }, [email])
  const handlePasswordBlur = useCallback(() => {
    updateLoginError(setFieldErrors, "password", requiredError("Password", password))
  }, [password])
  const handleTogglePassword = useCallback(() => {
    setShowPassword((current) => !current)
  }, [])
  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const visibleErrors = visibleLoginErrors(email, password)
      setFieldErrors(visibleErrors)
      if (Object.keys(visibleErrors).length > 0) {
        setError(null)
        return
      }
      setPending(true)
      setError(null)
      try {
        await login(email, password)
        onSuccess()
      } catch {
        setError(GENERIC_ERROR)
      } finally {
        setPending(false)
      }
    },
    [email, onSuccess, password],
  )

  return {
    email,
    password,
    error,
    fieldErrors,
    pending,
    showPassword,
    handleEmailChange,
    handlePasswordChange,
    handleEmailBlur,
    handlePasswordBlur,
    handleTogglePassword,
    handleSubmit,
  }
}
