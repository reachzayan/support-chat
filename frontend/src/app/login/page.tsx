"use client"

import { Effect, Exit } from "effect"
import { useRouter } from "next/navigation"
import { useCallback, useState, type ChangeEvent, type FormEvent } from "react"

import { login } from "@/lib/auth-client"
import { parseStaffEmail } from "@/lib/staff-email"

const GENERIC_ERROR = "Invalid email or password"

export default function LoginPage() {
  const router = useRouter()
  const handleSuccess = useCallback(() => {
    router.push("/admin/inbox")
  }, [router])
  return (
    <div className="bg-ice flex min-h-dvh flex-col">
      <header className="bg-navy-deep text-paper px-6 py-5">
        <p className="text-paper/60 text-[10px] font-medium tracking-[0.16em] uppercase">SupportChat</p>
        <p className="mt-1 text-sm font-medium tracking-wide">Screening operations</p>
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
  const [pending, setPending] = useState(false)

  const handleEmailChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value)
  }, [])
  const handlePasswordChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setPassword(event.target.value)
  }, [])
  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const parsed = Effect.runSyncExit(parseStaffEmail(email))
      if (Exit.isFailure(parsed)) {
        setError(GENERIC_ERROR)
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
      <div className="flex flex-col gap-4">
        <label className="text-ink flex flex-col gap-1 text-sm font-medium">
          Email
          <input
            type="email"
            name="email"
            autoComplete="username"
            value={email}
            onChange={handleEmailChange}
            className="border-line text-ink focus:border-steel focus:ring-steel rounded-[8px] border px-3 py-2 text-base font-normal outline-none focus:ring-2"
          />
        </label>
        <label className="text-ink flex flex-col gap-1 text-sm font-medium">
          Password
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={handlePasswordChange}
            className="border-line text-ink focus:border-steel focus:ring-steel rounded-[8px] border px-3 py-2 text-base font-normal outline-none focus:ring-2"
          />
        </label>
        {error ? <p className="text-ember text-sm">{error}</p> : null}
        <button
          type="submit"
          disabled={pending}
          className="bg-ember text-paper hover:bg-ember-mid disabled:bg-ember-soft rounded-[8px] px-4 py-2 text-sm font-semibold"
        >
          Sign in
        </button>
      </div>
    </form>
  )
}
