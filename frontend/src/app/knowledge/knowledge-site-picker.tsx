import { useCallback, useMemo } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { resolveKnowledgeSiteId, selectedSiteValue } from "./knowledge-site"

export const SitePicker = ({
  compact = false,
  sites,
  siteId,
  onSite,
}: {
  compact?: boolean
  sites: SiteRecord[]
  siteId: string
  onSite: (siteId: string) => void
}) => {
  const items = useMemo(
    () => Object.fromEntries(sites.map((site) => [site.id, site.name])),
    [sites],
  )
  const handleSiteChange = useCallback(
    (value: unknown) => {
      const selected = selectedSiteValue(value)
      if (selected === null) {
        return
      }
      const nextId = resolveKnowledgeSiteId(sites, selected, siteId)
      if (nextId === null) {
        return
      }
      onSite(nextId)
    },
    [onSite, siteId, sites],
  )
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${compact ? "w-44" : "sm:w-56"}`}>
      <label
        className={`${compact ? "sr-only" : "text-mute text-[10px] font-semibold tracking-[0.12em] uppercase"}`}
        htmlFor="knowledge-site"
      >
        Website
      </label>
      <Select
        value={siteId || null}
        onValueChange={handleSiteChange}
        items={items}
        id="knowledge-site"
      >
        <SelectTrigger
          aria-label="Site"
          className={`border-line bg-ice text-ink w-full min-w-0 cursor-pointer rounded-[9px] border px-3 text-sm ${compact ? "h-9 data-[size=default]:h-9" : "h-10 data-[size=default]:h-10"}`}
        >
          <SelectValue placeholder="Select a site" />
        </SelectTrigger>
        <SelectContent alignItemWithTrigger={false} align="start">
          <SelectGroup>
            {sites.map((site) => (
              <SelectItem key={site.id} value={site.id}>
                {site.name}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}
