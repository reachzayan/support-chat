"use client"

import { Plus } from "lucide-react"

import type { SiteRecord } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"

import { LABEL } from "./sites-shared"
import { SitesTable } from "./sites-table"

export const SitesDirectory = ({
  sites,
  isAdmin,
  checkingIds,
  onOpenAdd,
  onOpenManage,
  onCheckInstall,
}: {
  sites: SiteRecord[]
  isAdmin: boolean
  checkingIds: string[]
  onOpenAdd: () => void
  onOpenManage: (siteId: string) => void
  onCheckInstall: (siteId: string) => void
}) => (
  <section className="border-line bg-paper min-w-0 overflow-hidden rounded-lg border">
    <div className="border-line flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-5">
      <div>
        <p className={LABEL}>Directory</p>
        <p className="text-navy heading mt-0.5 text-sm">
          {sites.length === 1 ? "1 website" : `${sites.length} websites`}
        </p>
      </div>
      {isAdmin ? (
        <Button
          type="button"
          variant="default"
          size="lg"
          onClick={onOpenAdd}
          className="font-semibold"
        >
          <Plus data-icon="inline-start" aria-hidden="true" />
          Add new website
        </Button>
      ) : null}
    </div>

    {sites.length === 0 ? (
      <div className="px-6 py-16 text-center">
        <p className="text-navy heading text-sm">No sites configured</p>
        <p className="text-mute mt-2 text-sm">Add a site before installing the widget.</p>
      </div>
    ) : (
      <SitesTable
        sites={sites}
        isAdmin={isAdmin}
        onManage={onOpenManage}
        checkingIds={checkingIds}
        onCheckInstall={onCheckInstall}
      />
    )}
  </section>
)
