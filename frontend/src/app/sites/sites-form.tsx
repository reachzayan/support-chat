"use client"

import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FocusEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

import { BTN_PRIMARY, BTN_SECONDARY, FIELD } from "./sites-shared"

export const LeaveGuard = ({
  open,
  onStay,
  onLeave,
}: {
  open: boolean
  onStay: () => void
  onLeave: () => void
}) => {
  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) {
        onStay()
      }
    },
    [onStay],
  )

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent showCloseButton={false} className="max-w-md">
        <DialogHeader>
          <DialogTitle>Unsaved changes</DialogTitle>
          <DialogDescription>Do you want to leave? Your changes are not saved.</DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-row items-center justify-end gap-2 sm:flex-row">
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={onStay}
            className={BTN_SECONDARY}
          >
            Stay
          </Button>
          <Button
            type="button"
            variant="default"
            size="lg"
            onClick={onLeave}
            className={BTN_PRIMARY}
          >
            Leave
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export const useLeaveGuard = (dirty: boolean, onClose: () => void) => {
  const [leaveOpen, setLeaveOpen] = useState(false)
  const requestClose = useCallback(() => {
    if (dirty) {
      setLeaveOpen(true)
      return
    }
    onClose()
  }, [dirty, onClose])
  const handleStay = useCallback(() => setLeaveOpen(false), [])
  const handleLeave = useCallback(() => {
    setLeaveOpen(false)
    onClose()
  }, [onClose])
  return { leaveOpen, requestClose, handleStay, handleLeave }
}

export const useAnimatedDialogClose = (onClosed: () => void) => {
  const [open, setOpen] = useState(false)
  const closing = useRef(false)
  const timer = useRef<number | null>(null)
  const frame = useRef<number | null>(null)

  useEffect(() => {
    frame.current = window.requestAnimationFrame(() => {
      frame.current = null
      if (!closing.current) {
        setOpen(true)
      }
    })
    return () => {
      if (frame.current !== null) {
        window.cancelAnimationFrame(frame.current)
      }
    }
  }, [])

  const close = useCallback(
    (afterClose?: () => void) => {
      if (closing.current) {
        return
      }
      closing.current = true
      setOpen(false)
      timer.current = window.setTimeout(afterClose ?? onClosed, 220)
    },
    [onClosed],
  )
  useEffect(
    () => () => {
      if (frame.current !== null) {
        window.cancelAnimationFrame(frame.current)
      }
      if (timer.current !== null) {
        window.clearTimeout(timer.current)
      }
    },
    [],
  )
  return { open, close }
}

export const SiteField = ({
  id,
  label,
  value,
  disabled,
  onChange,
  error,
  onBlur,
}: {
  id: string
  label: string
  value: string
  disabled: boolean
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  error?: string
  onBlur?: (event: FocusEvent<HTMLInputElement>) => void
}) => {
  const errorId = `${id}-error`
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        name={id}
        autoComplete="off"
        value={value}
        disabled={disabled}
        onChange={onChange}
        onBlur={onBlur}
        className={FIELD}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={errorId}
      />
      <FieldError id={errorId}>{error}</FieldError>
    </Field>
  )
}

export const RouteSwitch = ({
  label,
  description,
  checked,
  disabled,
  ariaDisabled,
  onToggle,
  accent,
}: {
  label: string
  description: string
  checked: boolean
  disabled: boolean
  ariaDisabled: boolean
  onToggle: () => void
  accent: "steel" | "ember"
}) => {
  const trackOn = accent === "ember" ? "bg-ember" : "bg-steel"
  return (
    <Button
      type="button"
      variant="ghost"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      aria-disabled={ariaDisabled}
      disabled={disabled}
      onClick={onToggle}
      className="border-line bg-paper text-ink focus-visible:ring-steel flex min-h-14 cursor-pointer items-center justify-between gap-4 rounded-[8px] border px-3 py-3 text-left focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className="min-w-0">
        <span className="text-navy block text-sm font-medium">{label}</span>
        <span className="text-mute mt-0.5 block text-xs leading-5 font-normal">{description}</span>
      </span>
      <span
        aria-hidden="true"
        className={`relative h-6 w-10 shrink-0 rounded-[8px] ${checked ? trackOn : "bg-line"}`}
      >
        <span
          className={`bg-paper absolute top-0.5 size-5 rounded-[6px] shadow-sm motion-safe:transition-[left] motion-safe:duration-150 ${
            checked ? "left-4.5" : "left-0.5"
          }`}
        />
      </span>
    </Button>
  )
}
