"use client"

import { useCallback, useState } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"

import { AddSiteFields } from "./add-site-fields"
import { AddSiteInstallPanel } from "./add-site-install-panel"
import { LeaveGuard, useAnimatedDialogClose } from "./sites-form"
import { BTN_PRIMARY, BTN_SECONDARY } from "./sites-shared"
import { useAddSiteForm } from "./use-add-site-form"

// oxlint-disable-next-line max-lines-per-function, eslint/complexity
export const AddSiteModal = ({
  isAdmin,
  onClose,
  onCreated,
  onSaved,
}: {
  isAdmin: boolean
  onClose: () => void
  onCreated: (site: SiteRecord) => void
  onSaved: (site: SiteRecord) => void
}) => {
  const [error, setError] = useState<string | null>(null)
  const handleError = useCallback((message: string | null) => setError(message), [])
  const { open, close } = useAnimatedDialogClose(onClose)
  const form = useAddSiteForm(isAdmin, close, onCreated, onSaved, handleError)
  const created = form.created

  return (
    <>
      <Dialog open={open} onOpenChange={form.handleOpenChange}>
        <DialogContent className="max-h-[min(92vh,52rem)] max-w-3xl" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>{created ? "Install the widget" : "Add new website"}</DialogTitle>
            <DialogDescription>
              {created
                ? `Paste this snippet on ${created.name}, then recheck the install status.`
                : "Site key and public key are generated for you. Keep the public key in the embed snippet."}
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
            {created ? (
              <div className="flex flex-col">
                <AddSiteInstallPanel
                  site={created}
                  checking={form.checking}
                  onCheckInstall={form.handleCheckInstall}
                />
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <AddSiteFields
                  name={form.name}
                  greeting={form.greeting}
                  privacyUrl={form.privacyUrl}
                  websiteUrl={form.websiteUrl}
                  lockedOrigin={form.lockedOrigin}
                  originsText={form.originsText}
                  contactInfoText={form.contactInfoText}
                  onName={form.handleName}
                  onGreeting={form.handleGreeting}
                  onPrivacy={form.handlePrivacy}
                  onWebsiteUrl={form.handleWebsiteUrl}
                  onOrigins={form.handleOrigins}
                  onContactInfo={form.handleContactInfo}
                  errors={form.errors}
                  onNameBlur={form.handleNameBlur}
                  onPrivacyBlur={form.handlePrivacyBlur}
                  onWebsiteUrlBlur={form.handleWebsiteUrlBlur}
                  onOriginsBlur={form.handleOriginsBlur}
                />
              </div>
            )}
          </ScrollArea>
          <DialogFooter className="flex-row items-center justify-end gap-2">
            {created ? (
              <Button
                type="button"
                variant="default"
                size="lg"
                onClick={form.handleDone}
                className={BTN_PRIMARY}
              >
                Done
              </Button>
            ) : (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  onClick={form.requestClose}
                  className={BTN_SECONDARY}
                >
                  Close
                </Button>
                <Button
                  type="button"
                  variant="default"
                  size="lg"
                  onClick={form.handleSubmit}
                  className={BTN_PRIMARY}
                >
                  Create website
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <LeaveGuard open={form.leaveOpen} onStay={form.handleStay} onLeave={form.handleLeave} />
    </>
  )
}
