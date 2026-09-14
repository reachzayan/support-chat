"use client"

import type { SiteRecord } from "@/components/admin/staff-api"

import { BTN_PRIMARY, LABEL } from "./sites-shared"
import { SitesTable } from "./sites-table"

export const SitesDirectory = ({
  sites,
  isAdmin,
  onOpenAdd,
  onOpenManage,
}: {
  sites: SiteRecord[]
  isAdmin: boolean
  onOpenAdd: () => void
  onOpenManage: (siteId: string) => void
}) => (
  <section className="border-line bg-paper min-w-0 overflow-hidden rounded-[8px] border">
    <div className="border-line flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-5">
      <div>
        <p className={LABEL}>Directory</p>
        <p className="text-navy mt-0.5 text-sm font-extrabold">
          {sites.length === 1 ? "1 website" : `${sites.length} websites`}
        </p>
      </div>
      {isAdmin ? (
        <button type="button" onClick={onOpenAdd} className={BTN_PRIMARY}>
          Add new website
        </button>
      ) : null}
    </div>

    {sites.length === 0 ? (
      <div className="px-6 py-16 text-center">
        <p className="text-navy text-sm font-extrabold">No sites configured</p>
        <p className="text-mute mt-2 text-sm">Add a site before installing the widget.</p>
      </div>
    ) : (
      <SitesTable sites={sites} onManage={onOpenManage} />
    )}
  </section>
)
