"use client"

import { useCallback } from "react"

import { staffWrite, type SiteRecord } from "@/components/admin/staff-api"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { BTN_DANGER, BTN_SECONDARY } from "./sites-shared"

export const DeleteSiteModal = ({
  site,
  onClose,
  onDeleted,
  onError,
}: {
  site: SiteRecord
  onClose: () => void
  onDeleted: (siteId: string) => void
  onError: (message: string | null) => void
}) => {
  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) {
        onClose()
      }
    },
    [onClose],
  )
  const handleDelete = useCallback(async () => {
    const response = await staffWrite(`/api/sites/${site.id}`, "DELETE", {})
    if (!response.ok) {
      onError("Could not delete this site.")
      return
    }
    onError(null)
    onDeleted(site.id)
  }, [onDeleted, onError, site.id])

  return (
    <Dialog open onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md" showCloseButton>
        <DialogHeader>
          <DialogTitle>Delete site</DialogTitle>
          <DialogDescription>
            Delete {site.name}? This removes its chats, knowledge, and embed keys.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-row justify-end gap-2">
          <button type="button" onClick={onClose} className={BTN_SECONDARY}>
            Cancel
          </button>
          <button type="button" onClick={handleDelete} className={BTN_DANGER}>
            Delete site
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
