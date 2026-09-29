"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import { staffWrite } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { FieldError } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"

export type BlockVisitorTarget = {
  siteId: string
  visitorName: string
  email: string | null
  phone: string | null
  ip: string | null
}

type BlockVisitorDialogProps = {
  target: BlockVisitorTarget
  onClose: () => void
  onBlocked: (blockId: string) => void
}

const readCreatedBlockId = async (response: Response) => {
  const body = (await response.json()) as { id?: unknown }
  if (typeof body.id !== "string" || body.id.length === 0) {
    return null
  }
  return body.id
}

const blockPayload = (
  siteId: string,
  email: string | null,
  phone: string | null,
  ip: string | null,
  useEmail: boolean,
  usePhone: boolean,
  useIp: boolean,
) => ({
  site_id: siteId,
  email: useEmail ? email : null,
  phone: usePhone ? phone : null,
  ip: useIp ? ip : null,
})

const hasIdentifier = (payload: {
  email: string | null
  phone: string | null
  ip: string | null
}) => Boolean(payload.email || payload.phone || payload.ip)

const present = (value: string | null) => {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

// oxlint-disable-next-line eslint/max-lines-per-function -- Dialog fields, validation, and submit stay together.
export const BlockVisitorDialog = ({ target, onClose, onBlocked }: BlockVisitorDialogProps) => {
  const email = present(target.email)
  const phone = present(target.phone)
  const ip = present(target.ip)
  const [useEmail, setUseEmail] = useState(Boolean(email))
  const [usePhone, setUsePhone] = useState(Boolean(phone))
  const [useIp, setUseIp] = useState(Boolean(ip))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")

  const handleOpenChange = useCallback(
    (open: boolean) => {
      if (!open) {
        onClose()
      }
    },
    [onClose],
  )

  const handleBlock = useCallback(async () => {
    if (submitting) {
      return
    }
    const payload = blockPayload(target.siteId, email, phone, ip, useEmail, usePhone, useIp)
    if (!hasIdentifier(payload)) {
      setError("Select at least one identifier.")
      return
    }
    setSubmitting(true)
    setError("")
    try {
      const response = await staffWrite("/api/visitor-blocks", "POST", payload)
      if (!response.ok) {
        setError("The visitor could not be blocked. Try again.")
        return
      }
      const blockId = await readCreatedBlockId(response)
      if (blockId === null) {
        setError("The visitor could not be blocked. Try again.")
        return
      }
      onBlocked(blockId)
    } catch {
      setError("The visitor could not be blocked. Try again.")
    } finally {
      setSubmitting(false)
    }
  }, [email, ip, onBlocked, phone, submitting, target.siteId, useEmail, useIp, usePhone])

  const handleBlockClick = useCallback(() => {
    void handleBlock()
  }, [handleBlock])

  return (
    <Dialog open onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Block visitor</DialogTitle>
          <DialogDescription>
            Choose which identifiers to block for {target.visitorName} on this site. They will not
            be able to start or continue a chat here.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 px-5 py-5">
          <IdentifierCheck
            id="block-email"
            label="Email"
            value={email}
            checked={useEmail}
            onCheckedChange={setUseEmail}
          />
          <IdentifierCheck
            id="block-phone"
            label="Phone"
            value={phone}
            checked={usePhone}
            onCheckedChange={setUsePhone}
          />
          <IdentifierCheck
            id="block-ip"
            label="IP"
            value={ip}
            checked={useIp}
            onCheckedChange={setUseIp}
          />
          <FieldError>{error || undefined}</FieldError>
        </div>
        <DialogFooter className="flex-row items-center justify-end gap-2">
          <Button type="button" variant="outline" size="lg" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="default"
            size="lg"
            disabled={submitting}
            onClick={handleBlockClick}
          >
            {submitting ? <Spinner data-icon="inline-start" /> : null}
            {submitting ? "Blocking…" : "Block visitor"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const IdentifierCheck = ({
  id,
  label,
  value,
  checked,
  onCheckedChange,
}: {
  id: string
  label: string
  value: string | null
  checked: boolean
  onCheckedChange: (next: boolean) => void
}) => {
  const available = value !== null
  const handleChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      onCheckedChange(event.target.checked)
    },
    [onCheckedChange],
  )
  return (
    <div className="border-line bg-ice flex items-start gap-3 rounded-[8px] border px-3 py-2.5">
      <input
        id={id}
        type="checkbox"
        checked={available && checked}
        disabled={!available}
        onChange={handleChange}
        aria-label={label}
        className="border-line text-ember focus-visible:ring-steel mt-0.5 size-4 rounded-sm"
      />
      <label htmlFor={id} className="min-w-0">
        <span className="text-ink block text-sm font-medium">{label}</span>
        <span className="text-mute block font-mono text-xs">
          {available ? value : "Not available"}
        </span>
      </label>
    </div>
  )
}
