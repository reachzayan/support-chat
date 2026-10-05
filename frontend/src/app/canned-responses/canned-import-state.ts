import { useState, type ChangeEvent } from "react"

import { staffUpload } from "@/components/admin/staff-api"

export type PreviewRow = {
  action: string
  reason: string | null
  livechat_id: number | null
  group: number | null
  group_name: string | null
  livechat_website: string | null
  site_id: string | null
  shortcut: string
  excerpt: string
  bot_eligible: boolean
  disable_reason: string | null
}

export type PreviewPayload = {
  created: number
  updated: number
  skipped: number
  rows: PreviewRow[]
}

export type SiteOption = { id: string; name: string }
export type GroupTarget = string | "discard"

const LIVECHAT_GROUPS: Record<number, { name: string; website: string | null }> = {
  0: { name: "General", website: null },
  4: { name: "Sample Services", website: "sample-services.example.com" },
  5: { name: "Instant Check", website: "365instantcheck.com" },
  6: { name: "SampleSite", website: "sample-site.example.com" },
}

const errorMessage = async (response: Response) => {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail || "The file could not be imported. Try again."
  } catch {
    return "The file could not be imported. Try again."
  }
}

export const rowKey = (row: PreviewRow, index: number) => `${row.livechat_id ?? "row"}-${index}`

const isUnmappedSiteSkip = (row: PreviewRow) =>
  row.action === "skip" &&
  row.group != null &&
  /not a SupportChat (site|website)/i.test(row.reason || "")

const isMappableRow = (row: PreviewRow) =>
  row.group != null && (row.action !== "skip" || isUnmappedSiteSkip(row))

export const isHardSkip = (row: PreviewRow) => row.action === "skip" && !isUnmappedSiteSkip(row)

export const livechatGroupName = (group: number, rows: PreviewRow[]) =>
  rows[0]?.group_name || LIVECHAT_GROUPS[group]?.name || `group ${group}`

export const livechatGroupWebsite = (group: number, rows: PreviewRow[]) =>
  rows[0]?.livechat_website || LIVECHAT_GROUPS[group]?.website || null

export const groupedImportGroups = (rows: PreviewRow[]) => {
  const groups = new Map<number, PreviewRow[]>()
  for (const row of rows) {
    if (!isMappableRow(row) || row.group == null) continue
    const current = groups.get(row.group) ?? []
    current.push(row)
    groups.set(row.group, current)
  }
  return [...groups.entries()].toSorted((left, right) => left[0] - right[0])
}

const suggestedTarget = (group: number, rows: PreviewRow[]): GroupTarget | null => {
  if (group === 0) return "general"
  return rows.find((row) => row.site_id)?.site_id ?? null
}

const initialGroupTargets = (rows: PreviewRow[]) => {
  const targets: Record<number, GroupTarget> = {}
  for (const [group, groupRows] of groupedImportGroups(rows)) {
    const suggested = suggestedTarget(group, groupRows)
    if (suggested) targets[group] = suggested
  }
  return targets
}

export const updateIds = (rows: PreviewRow[]) =>
  rows
    .filter((row) => row.action === "update" && row.livechat_id != null)
    .map((row) => row.livechat_id as number)

const discardIdsFor = (
  rows: PreviewRow[],
  selected: Set<number>,
  groupTargets: Record<number, GroupTarget>,
) => {
  const discardIds: number[] = []
  for (const row of rows) {
    if (row.livechat_id == null) continue
    if (row.action === "update" && !selected.has(row.livechat_id)) {
      discardIds.push(row.livechat_id)
      continue
    }
    if (row.group == null) continue
    if (groupTargets[row.group] === "discard") discardIds.push(row.livechat_id)
  }
  return discardIds
}

const remapGroupsFor = (groupTargets: Record<number, GroupTarget>) => {
  const remapGroups: Record<string, string | null> = {}
  for (const [group, target] of Object.entries(groupTargets)) {
    if (target === "discard") continue
    remapGroups[group] = target === "general" ? null : target
  }
  return remapGroups
}

const buildDecisions = (
  rows: PreviewRow[],
  selected: Set<number>,
  groupTargets: Record<number, GroupTarget>,
) => ({
  discard_ids: discardIdsFor(rows, selected, groupTargets),
  remap_groups: remapGroupsFor(groupTargets),
})

export const unmappedGroupLabel = (group: number, rows: PreviewRow[]) => {
  const name = rows[0]?.group_name
  return name
    ? `Choose a website for ${name}, or discard those responses.`
    : `Choose a website for LiveChat group ${group}, or discard those responses.`
}

const hasPendingUnmapped = (
  groups: [number, PreviewRow[]][],
  groupTargets: Record<number, GroupTarget>,
) => groups.some(([group]) => groupTargets[group] == null)

// oxlint-disable-next-line eslint/max-lines-per-function -- Preview, remap, and commit stay in one hook so the file is not re-selected between steps.
export const useImportDialog = ({
  onClose,
  onImported,
}: {
  onClose: () => void
  onImported: () => Promise<void>
}) => {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<PreviewPayload | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [groupTargets, setGroupTargets] = useState<Record<number, GroupTarget>>({})
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const clearPlan = () => {
    setPreview(null)
    setSelected(new Set())
    setGroupTargets({})
  }
  const handleClose = () => {
    if (busy) return
    setFile(null)
    clearPlan()
    setError("")
    onClose()
  }
  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null)
    clearPlan()
    setError("")
  }
  return {
    file,
    preview,
    selected,
    groupTargets,
    error,
    busy,
    setSelected,
    setGroupTargets,
    handleClose,
    handleFile,
    handlePreview: async () => {
      if (!file || busy) return
      setBusy(true)
      setError("")
      try {
        const response = await staffUpload("/api/canned-replies/import/preview", file)
        if (!response.ok) {
          setError(await errorMessage(response))
          return
        }
        const payload = (await response.json()) as PreviewPayload
        setPreview(payload)
        setSelected(new Set(updateIds(payload.rows)))
        setGroupTargets(initialGroupTargets(payload.rows))
      } catch {
        setError("The file could not be read. Try again.")
      } finally {
        setBusy(false)
      }
    },
    handleImport: async () => {
      if (!file || !preview || busy) return
      if (hasPendingUnmapped(groupedImportGroups(preview.rows), groupTargets)) return
      setBusy(true)
      setError("")
      try {
        const response = await staffUpload("/api/canned-replies/import", file, {
          decisions: JSON.stringify(buildDecisions(preview.rows, selected, groupTargets)),
        })
        if (!response.ok) {
          setError(await errorMessage(response))
          return
        }
        await onImported()
        setFile(null)
        clearPlan()
        onClose()
      } catch {
        setError("The file could not be imported. Try again.")
      } finally {
        setBusy(false)
      }
    },
    canImport:
      !!preview && !busy && !hasPendingUnmapped(groupedImportGroups(preview.rows), groupTargets),
  }
}
