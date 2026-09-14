"use client"

import { useCallback, useState } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { AddSiteFields } from "./add-site-fields"
import { LeaveGuard, useAnimatedDialogClose } from "./sites-form"
import { BTN_PRIMARY, BTN_SECONDARY } from "./sites-shared"
import { useAddSiteForm } from "./use-add-site-form"

export const AddSiteModal = ({
  isAdmin,
  onClose,
  onCreated,
}: {
  isAdmin: boolean
  onClose: () => void
  onCreated: (site: SiteRecord) => void
}) => {
  const [error, setError] = useState<string | null>(null)
  const handleError = useCallback((message: string | null) => setError(message), [])
  const { open, close } = useAnimatedDialogClose(onClose)
  const form = useAddSiteForm(isAdmin, close, onCreated, handleError)

  return (
    <>
      <Dialog open={open} onOpenChange={form.handleOpenChange}>
        <DialogContent className="max-h-[min(92vh,52rem)] max-w-3xl" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Add new website</DialogTitle>
            <DialogDescription>
              Site key and public key are generated for you. Keep the public key in the embed
              snippet.
            </DialogDescription>
          </DialogHeader>
          {error ? (
            <p
              className="border-ember/20 bg-ember/10 text-ember mx-5 mt-4 rounded-lg border px-3 py-2.5 text-xs leading-5"
              role="alert"
            >
              {error}
            </p>
          ) : null}
          <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-5 py-4">
            <AddSiteFields
              name={form.name}
              greeting={form.greeting}
              privacyUrl={form.privacyUrl}
              originsText={form.originsText}
              onName={form.handleName}
              onGreeting={form.handleGreeting}
              onPrivacy={form.handlePrivacy}
              onOrigins={form.handleOrigins}
              errors={form.errors}
              onNameBlur={form.handleNameBlur}
              onPrivacyBlur={form.handlePrivacyBlur}
              onOriginsBlur={form.handleOriginsBlur}
            />
          </div>
          <DialogFooter className="flex-row justify-end gap-2">
            <button type="button" onClick={form.requestClose} className={BTN_SECONDARY}>
              Close
            </button>
            <button type="button" onClick={form.handleSubmit} className={BTN_PRIMARY}>
              Create website
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <LeaveGuard open={form.leaveOpen} onStay={form.handleStay} onLeave={form.handleLeave} />
    </>
  )
}
