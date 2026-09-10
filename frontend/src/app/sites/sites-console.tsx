"use client"

import { useMemo } from "react"

import { StaffHeader } from "@/components/admin/staff-nav"

import { SitesConsoleModals } from "./sites-console-modals"
import { SitesDirectory } from "./sites-directory"
import { useSitesConsoleActions } from "./use-sites-console-actions"
import { useSitesList } from "./use-sites-list"

type SitesConsoleProps = {
  isAdmin: boolean
  displayName: string
}

export const SitesConsole = ({ isAdmin, displayName: _displayName }: SitesConsoleProps) => {
  const { sites, setSites, error, setError } = useSitesList()
  const actions = useSitesConsoleActions(setSites, setError)

  const activeSite = useMemo(
    () => sites.find((row) => row.id === actions.activeId) ?? null,
    [actions.activeId, sites],
  )

  return (
    <div className="bg-ice min-h-0 flex-1 overflow-y-auto">
      <StaffHeader
        eyebrow="Workspace / Sites"
        title="Sites"
        description="Each brand keeps its own widget key, host allowlist, and specialist routing."
      />
      <div
        id="main-content"
        className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-5 py-6 lg:px-8 lg:py-8"
      >
        {error ? (
          <p
            className="border-ember/20 bg-ember/10 text-ember rounded-[8px] border px-4 py-3 text-sm"
            role="alert"
          >
            {error}
          </p>
        ) : null}

        <SitesDirectory
          sites={sites}
          isAdmin={isAdmin}
          onOpenAdd={actions.handleOpenAdd}
          onOpenManage={actions.handleOpenManage}
        />
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
        onError={setError}
      />
    </div>
  )
}
