"use client"

import type { ChangeEvent } from "react"

import { Button } from "@/components/ui/button"
import { FieldError } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { StateIcon } from "@/components/ui/state-icon"

const FIELD =
  "border-line bg-ice text-ink focus:border-steel focus:ring-steel h-12 rounded-lg border px-4 text-base font-normal shadow-none outline-none transition-[border-color,box-shadow] duration-200 ease-out focus:ring-2 dark:bg-ice-2"

export const LoginFields = ({
  email,
  password,
  showPassword,
  fieldErrors,
  onEmailChange,
  onPasswordChange,
  onEmailBlur,
  onPasswordBlur,
  onTogglePassword,
}: {
  email: string
  password: string
  showPassword: boolean
  fieldErrors: Record<string, string>
  onEmailChange: (event: ChangeEvent<HTMLInputElement>) => void
  onPasswordChange: (event: ChangeEvent<HTMLInputElement>) => void
  onEmailBlur: () => void
  onPasswordBlur: () => void
  onTogglePassword: () => void
}) => (
  <div className="flex flex-col gap-1">
    <EmailField
      email={email}
      error={fieldErrors.email}
      onChange={onEmailChange}
      onBlur={onEmailBlur}
    />
    <PasswordField
      password={password}
      showPassword={showPassword}
      error={fieldErrors.password}
      onChange={onPasswordChange}
      onBlur={onPasswordBlur}
      onTogglePassword={onTogglePassword}
    />
  </div>
)

const EmailField = ({
  email,
  error,
  onChange,
  onBlur,
}: {
  email: string
  error?: string
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  onBlur: () => void
}) => (
  <div className="text-ink flex flex-col gap-1.5 text-sm font-medium">
    <label htmlFor="login-email">Email</label>
    <Input
      id="login-email"
      type="email"
      name="email"
      autoComplete="username"
      value={email}
      onChange={onChange}
      onBlur={onBlur}
      className={FIELD}
      aria-invalid={error ? "true" : undefined}
      aria-describedby="login-email-error"
    />
    <FieldError id="login-email-error">{error}</FieldError>
  </div>
)

const PasswordField = ({
  password,
  showPassword,
  error,
  onChange,
  onBlur,
  onTogglePassword,
}: {
  password: string
  showPassword: boolean
  error?: string
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  onBlur: () => void
  onTogglePassword: () => void
}) => (
  <div className="text-ink flex flex-col gap-1.5 text-sm font-medium">
    <label htmlFor="login-password">Password</label>
    <div className="relative">
      <Input
        id="login-password"
        type={showPassword ? "text" : "password"}
        name="password"
        autoComplete="current-password"
        value={password}
        onChange={onChange}
        onBlur={onBlur}
        className={`${FIELD} pr-12`}
        aria-invalid={error ? "true" : undefined}
        aria-describedby="login-password-error"
      />
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        onClick={onTogglePassword}
        aria-label={showPassword ? "Hide password" : "Show password"}
        aria-pressed={showPassword}
        className="text-mute hover:text-ink absolute top-1/2 right-1.5 -translate-y-1/2 rounded-xl"
      >
        {showPassword ? <StateIcon name="eye-slash" /> : <StateIcon name="eye" />}
      </Button>
    </div>
    <FieldError id="login-password-error">{error}</FieldError>
  </div>
)
