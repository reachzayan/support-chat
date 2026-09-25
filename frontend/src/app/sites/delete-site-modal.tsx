"use client"

import { useCallback, useState } from "react"

import { staffWrite, type SiteRecord } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { useAnimatedDialogClose } from "./sites-form"
import { BTN_DANGER, BTN_SECONDARY } from "./sites-shared"

export const DeleteSiteModal = ({
  site,
  onClose,
  onDeleted,
}: {
  site: SiteRecord
  onClose: () => void
  onDeleted: (siteId: string) => void
}) => {
  const [error, setError] = useState<string | null>(null)
  const { open, close } = useAnimatedDialogClose(onClose)
  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) {
        close()
      }
    },
    [close],
  )
  const handleDelete = useCallback(async () => {
    const response = await staffWrite(`/api/sites/${site.id}`, "DELETE", {})
    if (!response.ok) {
      setError("Could not delete this site.")
      return
    }
    close(() => onDeleted(site.id))
  }, [close, onDeleted, site.id])
  const handleCancel = useCallback(() => {
    close()
  }, [close])

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md" showCloseButton>
        <DialogHeader>
          <DialogTitle>Delete site</DialogTitle>
          <DialogDescription>
            Delete {site.name}? This removes its chats, knowledge, and embed keys.
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
        <DialogFooter className="flex-row items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={handleCancel}
            className={BTN_SECONDARY}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="lg"
            onClick={handleDelete}
            className={BTN_DANGER}
          >
            Delete site
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
