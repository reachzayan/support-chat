"use client"

import { Effect, Exit } from "effect"
import { useRouter } from "next/navigation"
import {
  useCallback,
  useState,
  type ChangeEvent,
  type Dispatch,
  type FormEvent,
  type SetStateAction,
} from "react"

import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { login } from "@/lib/auth-client"
import { parseStaffEmail } from "@/lib/staff-email"
import { emailError, requiredError } from "@/lib/validation"

const GENERIC_ERROR = "Invalid email or password"

const updateLoginError = (
  setFieldErrors: Dispatch<SetStateAction<Record<string, string>>>,
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

export default function LoginPage() {
  const router = useRouter()
  const handleSuccess = useCallback(() => {
    router.push("/admin/inbox")
  }, [router])
  return (
    <div className="bg-ice flex min-h-dvh flex-col">
      <header className="bg-navy-deep flex items-center justify-between px-6 py-5 text-white">
        <div>
          <p className="text-[10px] font-medium tracking-[0.16em] text-white/60 uppercase">
            SupportChat
          </p>
          <p className="mt-1 text-sm font-medium tracking-wide">Screening operations</p>
        </div>
        <ThemeToggle compact />
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-16">
        <LoginForm onSuccess={handleSuccess} />
      </main>
    </div>
  )
}

const LoginForm = ({ onSuccess }: { onSuccess: () => void }) => {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)

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

  return (
    <form
      method="post"
      action="/login"
      onSubmit={handleSubmit}
      className="border-line bg-paper w-full max-w-sm rounded-[8px] border p-6 shadow-sm"
    >
      <h1 className="text-navy mb-1 text-2xl font-semibold">Sign in</h1>
      <p className="text-mute mb-6 text-sm">Invited specialists only.</p>
      <LoginFields
        email={email}
        password={password}
        fieldErrors={fieldErrors}
        onEmailChange={handleEmailChange}
        onPasswordChange={handlePasswordChange}
        onEmailBlur={handleEmailBlur}
        onPasswordBlur={handlePasswordBlur}
      />
      <div className="flex flex-col gap-4">
        {error ? (
          <p className="text-ember text-sm" role="alert">
            {error}
          </p>
        ) : null}
        <Button
          type="submit"
          disabled={pending}
          className="bg-ember hover:bg-ember-mid disabled:bg-ember-soft dark:text-navy-deep rounded-[8px] px-4 py-2 text-sm font-semibold text-white"
        >
          Sign in
        </Button>
      </div>
    </form>
  )
}

const LoginFields = ({
  email,
  password,
  fieldErrors,
  onEmailChange,
  onPasswordChange,
  onEmailBlur,
  onPasswordBlur,
}: {
  email: string
  password: string
  fieldErrors: Record<string, string>
  onEmailChange: (event: ChangeEvent<HTMLInputElement>) => void
  onPasswordChange: (event: ChangeEvent<HTMLInputElement>) => void
  onEmailBlur: () => void
  onPasswordBlur: () => void
}) => (
  <div className="flex flex-col gap-4">
    <div className="text-ink flex flex-col gap-1 text-sm font-medium">
      <label htmlFor="login-email">Email</label>
      <Input
        id="login-email"
        type="email"
        name="email"
        autoComplete="username"
        value={email}
        onChange={onEmailChange}
        onBlur={onEmailBlur}
        className="border-line text-ink focus:border-steel focus:ring-steel rounded-[8px] border px-3 py-2 text-base font-normal outline-none focus:ring-2"
        aria-invalid={fieldErrors.email ? "true" : undefined}
        aria-describedby={fieldErrors.email ? "login-email-error" : undefined}
      />
      {fieldErrors.email ? (
        <FieldError id="login-email-error">{fieldErrors.email}</FieldError>
      ) : null}
    </div>
    <div className="text-ink flex flex-col gap-1 text-sm font-medium">
      <label htmlFor="login-password">Password</label>
      <Input
        id="login-password"
        type="password"
        name="password"
        autoComplete="current-password"
        value={password}
        onChange={onPasswordChange}
        onBlur={onPasswordBlur}
        className="border-line text-ink focus:border-steel focus:ring-steel rounded-[8px] border px-3 py-2 text-base font-normal outline-none focus:ring-2"
        aria-invalid={fieldErrors.password ? "true" : undefined}
        aria-describedby={fieldErrors.password ? "login-password-error" : undefined}
      />
      {fieldErrors.password ? (
        <FieldError id="login-password-error">{fieldErrors.password}</FieldError>
      ) : null}
    </div>
  </div>
)

const FieldError = ({ id, children }: { id: string; children: string }) => (
  <span id={id} className="text-ember text-xs font-normal" role="alert">
    {children}
  </span>
)
