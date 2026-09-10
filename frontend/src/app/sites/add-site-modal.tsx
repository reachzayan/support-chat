"use client"

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
import { LeaveGuard } from "./sites-form"
import { BTN_PRIMARY, BTN_SECONDARY } from "./sites-shared"
import { useAddSiteForm } from "./use-add-site-form"

export const AddSiteModal = ({
  isAdmin,
  onClose,
  onCreated,
  onError,
}: {
  isAdmin: boolean
  onClose: () => void
  onCreated: (site: SiteRecord) => void
  onError: (message: string | null) => void
}) => {
  const form = useAddSiteForm(isAdmin, onClose, onCreated, onError)

  return (
    <>
      <Dialog open onOpenChange={form.handleOpenChange}>
        <DialogContent className="max-h-[min(92vh,52rem)] max-w-3xl" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Add new website</DialogTitle>
            <DialogDescription>
              Site key and public key are generated for you. Keep the public key in the embed
              snippet.
            </DialogDescription>
          </DialogHeader>
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
