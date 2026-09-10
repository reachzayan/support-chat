"use client"

import { useCallback } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { ManageSiteFields, ManageSiteSnippet } from "./manage-site-fields"
import { ManageSiteRouting } from "./manage-site-routing"
import { OffBrandEditor } from "./off-brand-editor"
import { LeaveGuard } from "./sites-form"
import { BTN_DANGER, BTN_PRIMARY, BTN_SECONDARY } from "./sites-shared"
import { useManageSiteForm } from "./use-manage-site-form"

export const ManageSiteModal = ({
  site,
  isAdmin,
  onClose,
  onSaved,
  onError,
  onRequestDelete,
}: {
  site: SiteRecord
  isAdmin: boolean
  onClose: () => void
  onSaved: (site: SiteRecord) => void
  onError: (message: string | null) => void
  onRequestDelete: (siteId: string) => void
}) => {
  const form = useManageSiteForm(site, onClose, onSaved, onError)
  const handleRequestDelete = useCallback(
    () => onRequestDelete(site.id),
    [onRequestDelete, site.id],
  )
  const publicPreview = `${site.public_key.slice(0, 8)}…${site.public_key.slice(-8)}`

  return (
    <>
      <Dialog open onOpenChange={form.handleOpenChange}>
        <DialogContent className="max-h-[min(92vh,56rem)] max-w-4xl" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Manage site</DialogTitle>
            <DialogDescription>
              Keys are issued by the server. Site key {site.key}. Public key {publicPreview}.
            </DialogDescription>
          </DialogHeader>
          <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-4">
            <ManageSiteFields
              site={site}
              isAdmin={isAdmin}
              name={form.name}
              greeting={form.greeting}
              privacyUrl={form.privacyUrl}
              originsText={form.originsText}
              windowHours={form.windowHours}
              onName={form.handleName}
              onGreeting={form.handleGreeting}
              onPrivacy={form.handlePrivacy}
              onOrigins={form.handleOrigins}
              onWindow={form.handleWindow}
            />
            <ManageSiteRouting site={site} isAdmin={isAdmin} onSaved={onSaved} onError={onError} />
            <OffBrandEditor site={site} isAdmin={isAdmin} onError={onError} onSaved={onSaved} />
            <ManageSiteSnippet site={site} copyNotice={form.copyNotice} onCopy={form.handleCopy} />
          </div>
          <DialogFooter className="flex-row justify-end gap-2">
            {isAdmin ? (
              <button
                type="button"
                onClick={handleRequestDelete}
                className={`${BTN_DANGER} mr-auto`}
              >
                Delete
              </button>
            ) : null}
            <button type="button" onClick={form.requestClose} className={BTN_SECONDARY}>
              Close
            </button>
            {isAdmin ? (
              <button type="button" onClick={form.handleSave} className={BTN_PRIMARY}>
                Save
              </button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <LeaveGuard open={form.leaveOpen} onStay={form.handleStay} onLeave={form.handleLeave} />
    </>
  )
}
