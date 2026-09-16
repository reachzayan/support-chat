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
import { ScrollArea } from "@/components/ui/scroll-area"

import { ManageSiteFields, ManageSiteSnippet } from "./manage-site-fields"
import { ManageSiteRouting } from "./manage-site-routing"
import { OffBrandEditor } from "./off-brand-editor"
import { LeaveGuard, useAnimatedDialogClose } from "./sites-form"
import { BTN_DANGER, BTN_PRIMARY, BTN_SECONDARY } from "./sites-shared"
import { useManageSiteForm } from "./use-manage-site-form"

// oxlint-disable-next-line max-lines-per-function
export const ManageSiteModal = ({
  site,
  isAdmin,
  onClose,
  onSaved,
  onRequestDelete,
}: {
  site: SiteRecord
  isAdmin: boolean
  onClose: () => void
  onSaved: (site: SiteRecord) => void
  onRequestDelete: (siteId: string) => void
}) => {
  const [error, setError] = useState<string | null>(null)
  const handleError = useCallback((message: string | null) => setError(message), [])
  const { open, close } = useAnimatedDialogClose(onClose)
  const form = useManageSiteForm(site, close, onSaved, handleError)
  const handleRequestDelete = useCallback(
    () => close(() => onRequestDelete(site.id)),
    [close, onRequestDelete, site.id],
  )
  const publicPreview = `${site.public_key.slice(0, 8)}…${site.public_key.slice(-8)}`

  return (
    <>
      <Dialog open={open} onOpenChange={form.handleOpenChange}>
        <DialogContent className="max-h-[min(92vh,56rem)] max-w-4xl" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Manage site</DialogTitle>
            <DialogDescription>
              Keys are issued by the server. Site key {site.key}. Public key {publicPreview}.
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
          <ScrollArea className="min-h-0 flex-1 px-5 py-4">
            <div className="flex flex-col gap-5">
              <ManageSiteFields
                site={site}
                isAdmin={isAdmin}
                name={form.name}
                greeting={form.greeting}
                privacyUrl={form.privacyUrl}
                websiteUrl={form.websiteUrl}
                originsText={form.originsText}
                contactInfoText={form.contactInfoText}
                windowHours={form.windowHours}
                onName={form.handleName}
                onGreeting={form.handleGreeting}
                onPrivacy={form.handlePrivacy}
                onWebsiteUrl={form.handleWebsiteUrl}
                onOrigins={form.handleOrigins}
                onContactInfo={form.handleContactInfo}
                onWindow={form.handleWindow}
                errors={form.errors}
                onNameBlur={form.handleNameBlur}
                onPrivacyBlur={form.handlePrivacyBlur}
                onWebsiteUrlBlur={form.handleWebsiteUrlBlur}
                onOriginsBlur={form.handleOriginsBlur}
              />
              <ManageSiteRouting
                site={site}
                isAdmin={isAdmin}
                onSaved={onSaved}
                onError={handleError}
              />
              <OffBrandEditor
                site={site}
                isAdmin={isAdmin}
                onError={handleError}
                onSaved={onSaved}
              />
              <ManageSiteSnippet
                site={site}
                copyNotice={form.copyNotice}
                onCopy={form.handleCopy}
              />
            </div>
          </ScrollArea>
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
