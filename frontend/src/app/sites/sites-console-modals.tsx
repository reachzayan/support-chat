"use client"

import type { SiteRecord } from "@/components/admin/staff-api"

import { AddSiteModal, DeleteSiteModal, ManageSiteModal } from "./sites-modals"
import type { ModalKind } from "./sites-shared"

export const SitesConsoleModals = ({
  modal,
  activeSite,
  isAdmin,
  onClose,
  onCreated,
  onSaved,
  onDeleted,
  onRequestDelete,
}: {
  modal: ModalKind
  activeSite: SiteRecord | null
  isAdmin: boolean
  onClose: () => void
  onCreated: (site: SiteRecord) => void
  onSaved: (site: SiteRecord) => void
  onDeleted: (siteId: string) => void
  onRequestDelete: (siteId: string) => void
}) => (
  <>
    {modal === "add" ? (
      <AddSiteModal isAdmin={isAdmin} onClose={onClose} onCreated={onCreated} />
    ) : null}
    {activeSite && modal === "manage" ? (
      <ManageSiteModal
        site={activeSite}
        isAdmin={isAdmin}
        onClose={onClose}
        onSaved={onSaved}
        onRequestDelete={onRequestDelete}
      />
    ) : null}
    {activeSite && modal === "delete" ? (
      <DeleteSiteModal site={activeSite} onClose={onClose} onDeleted={onDeleted} />
    ) : null}
  </>
)
