"use client"

import { useMemo } from "react"

import { RetryError } from "@/components/admin/retry-error"
import { StaffHeader } from "@/components/admin/staff-nav"
import { useSearchTarget, useOpenSearchTarget } from "@/components/search/workspace-route"

import { SitesConsoleModals } from "./sites-console-modals"
import { SitesDirectory } from "./sites-directory"
import { useSitesConsoleActions } from "./use-sites-console-actions"
import { useSitesList } from "./use-sites-list"

type SitesConsoleProps = {
  isAdmin: boolean
  displayName: string
}

export const SitesConsole = ({ isAdmin, displayName: _displayName }: SitesConsoleProps) => {
  const { sites, loaded, setSites, error, setError, handleRetry } = useSitesList()
  const actions = useSitesConsoleActions(setSites, setError)
  const target = useSearchTarget()
  useOpenSearchTarget(target.site, loaded ? sites : null, (site) =>
    actions.handleOpenManage(site.id),
  )

  const activeSite = useMemo(
    () => sites.find((row) => row.id === actions.activeId) ?? null,
    [actions.activeId, sites],
  )

  return (
    <div className="view-transition-enter bg-ice min-h-0 min-w-0 flex-1 overflow-y-auto">
      <StaffHeader
        title="Sites"
        description="Each brand keeps its own widget key, host allowlist, and specialist routing."
      />
      <div
        id="main-content"
        className="flex w-full min-w-0 flex-col gap-4 px-4 py-4 sm:px-5 sm:py-6 lg:px-8 lg:py-8"
      >
        {error === "Sites could not be loaded" ? (
          <RetryError text={error} onRetry={handleRetry} />
        ) : error && actions.modal === null ? (
          <p
            className="border-ember/20 bg-ember/10 text-ember rounded-[8px] border px-4 py-3 text-sm"
            role="alert"
          >
            {error}
          </p>
        ) : null}

        {error === "Sites could not be loaded" && sites.length === 0 ? null : (
          <SitesDirectory
            sites={sites}
            isAdmin={isAdmin}
            checkingIds={actions.checkingIds}
            onOpenAdd={actions.handleOpenAdd}
            onOpenManage={actions.handleOpenManage}
            onCheckInstall={actions.handleCheckInstall}
          />
        )}
      </div>

      <SitesConsoleModals
        modal={actions.modal}
        activeSite={activeSite}
        isAdmin={isAdmin}
        onClose={actions.handleCloseModal}
        onCreated={actions.handleCreated}
        onSaved={actions.handleSaved}
        onDeleted={actions.handleDeleted}
        onRequestDelete={actions.handleOpenDelete}
      />
    </div>
  )
}
