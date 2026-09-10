"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { BTN_PRIMARY, BTN_SECONDARY, FIELD, LABEL } from "./sites-shared"

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
        <DialogFooter className="flex-row justify-end gap-2 sm:flex-row">
          <button type="button" onClick={onStay} className={BTN_SECONDARY}>
            Stay
          </button>
          <button type="button" onClick={onLeave} className={BTN_PRIMARY}>
            Leave
          </button>
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

export const Field = ({
  id,
  label,
  value,
  disabled,
  onChange,
}: {
  id: string
  label: string
  value: string
  disabled: boolean
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
}) => {
  return (
    <div>
      <label className={LABEL} htmlFor={id}>
        {label}
      </label>
      <input id={id} value={value} disabled={disabled} onChange={onChange} className={FIELD} />
    </div>
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
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      aria-disabled={ariaDisabled}
      disabled={disabled}
      onClick={onToggle}
      className="border-line bg-paper text-ink focus-visible:ring-steel flex min-h-14 cursor-pointer items-center justify-between gap-4 rounded-[8px] border px-3 py-3 text-left focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className="min-w-0">
        <span className="text-navy block text-sm font-bold">{label}</span>
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
    </button>
  )
}
