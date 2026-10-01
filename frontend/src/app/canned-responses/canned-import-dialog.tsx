/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-array-as-prop, react/no-array-index-key -- Dialog callbacks and Base UI render props use live import state. */

import { useState, type ChangeEvent, type ReactNode } from "react"

import { staffUpload } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogResizeSection,
  DialogTitle,
} from "@/components/ui/dialog"
import { Spinner } from "@/components/ui/spinner"

import { CannedResponseSelect, scopeOptions } from "./canned-response-select"

type PreviewRow = {
  action: string
  reason: string | null
  livechat_id: number | null
  group: number | null
  group_name: string | null
  shortcut: string
  excerpt: string
  bot_eligible: boolean
  disable_reason: string | null
}

type PreviewPayload = {
  created: number
  updated: number
  skipped: number
  rows: PreviewRow[]
}

type SiteOption = { id: string; name: string }
type GroupTarget = string | "discard"

const errorMessage = async (response: Response) => {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail || "The file could not be imported. Try again."
  } catch {
    return "The file could not be imported. Try again."
  }
}

const rowKey = (row: PreviewRow, index: number) => `${row.livechat_id ?? "row"}-${index}`

const groupedUnmapped = (rows: PreviewRow[]) => {
  const groups = new Map<number, PreviewRow[]>()
  for (const row of rows) {
    if (row.action !== "unmapped" || row.group == null) continue
    const current = groups.get(row.group) ?? []
    current.push(row)
    groups.set(row.group, current)
  }
  return [...groups.entries()]
}

const updateIds = (rows: PreviewRow[]) =>
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
    if (row.action !== "unmapped" || row.group == null) continue
    const target = groupTargets[row.group]
    if (target === "discard" || target == null) discardIds.push(row.livechat_id)
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

const pendingUnmappedLabel = (
  groups: [number, PreviewRow[]][],
  groupTargets: Record<number, GroupTarget>,
) => {
  const pending = groups.find(([group]) => groupTargets[group] == null)
  if (!pending) return ""
  const name = pending[1][0]?.group_name
  return name
    ? `Choose a website for ${name}, or discard those responses.`
    : `Choose a website for LiveChat group ${pending[0]}, or discard those responses.`
}

// oxlint-disable-next-line eslint/max-lines-per-function -- Preview, remap, and commit stay in one hook so the file is not re-selected between steps.
const useImportDialog = ({
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
        setGroupTargets({})
      } catch {
        setError("The file could not be read. Try again.")
      } finally {
        setBusy(false)
      }
    },
    handleImport: async () => {
      if (!file || !preview || busy) return
      const pending = pendingUnmappedLabel(groupedUnmapped(preview.rows), groupTargets)
      if (pending) {
        setError(pending)
        return
      }
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
  }
}

export const ImportDialog = ({
  open,
  onClose,
  onImported,
  sites,
}: {
  open: boolean
  onClose: () => void
  onImported: () => Promise<void>
  sites: SiteOption[]
}) => {
  const dialog = useImportDialog({ onClose, onImported })
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) dialog.handleClose()
      }}
    >
      <DialogContent className="max-h-[min(92vh,56rem)] max-w-3xl">
        <DialogHeader>
          <DialogTitle>Import LiveChat canned responses</DialogTitle>
          <DialogDescription>
            Choose a LiveChat canned responses CSV. Preview the rows, then import them into this
            library.
          </DialogDescription>
        </DialogHeader>
        <DialogResizeSection className="flex min-h-0 flex-col gap-3 px-5 py-3">
          <label className="text-ink flex flex-col gap-1.5 text-sm font-medium">
            CSV file
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={dialog.handleFile}
              aria-label="LiveChat canned responses CSV"
              className="text-ink file:border-line file:bg-ice file:text-navy text-sm file:mr-3 file:rounded-[8px] file:border file:px-3 file:py-1.5 file:text-xs file:font-bold"
            />
          </label>
          {dialog.preview ? (
            <PreviewBody
              preview={dialog.preview}
              sites={sites}
              selected={dialog.selected}
              groupTargets={dialog.groupTargets}
              onSelected={dialog.setSelected}
              onGroupTarget={(group, target) =>
                dialog.setGroupTargets((current) => ({ ...current, [group]: target }))
              }
            />
          ) : null}
          {dialog.error ? <p className="text-ember text-sm">{dialog.error}</p> : null}
        </DialogResizeSection>
        <DialogFooter className="flex-row items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={dialog.handleClose}>
            Cancel
          </Button>
          {dialog.preview ? (
            <Button
              variant="default"
              disabled={dialog.busy}
              onClick={() => void dialog.handleImport()}
            >
              {dialog.busy ? <Spinner data-icon="inline-start" /> : null}
              {dialog.busy ? "Importing…" : "Import responses"}
            </Button>
          ) : (
            <Button
              variant="default"
              disabled={!dialog.file || dialog.busy}
              onClick={() => void dialog.handlePreview()}
            >
              {dialog.busy ? <Spinner data-icon="inline-start" /> : null}
              {dialog.busy ? "Reading…" : "Preview"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// oxlint-disable-next-line eslint/max-lines-per-function -- Grouped preview sections stay together for one reviewable import.
const PreviewBody = ({
  preview,
  sites,
  selected,
  groupTargets,
  onSelected,
  onGroupTarget,
}: {
  preview: PreviewPayload
  sites: SiteOption[]
  selected: Set<number>
  groupTargets: Record<number, GroupTarget>
  onSelected: (next: Set<number>) => void
  onGroupTarget: (group: number, target: GroupTarget) => void
}) => {
  const creates = preview.rows.filter((row) => row.action === "create" && row.bot_eligible)
  const disabled = preview.rows.filter((row) => row.action === "create" && !row.bot_eligible)
  const updates = preview.rows.filter((row) => row.action === "update")
  const unchanged = preview.rows.filter((row) => row.action === "unchanged")
  const skipped = preview.rows.filter((row) => row.action === "skip")
  const unmapped = groupedUnmapped(preview.rows)
  const ids = updateIds(preview.rows)
  return (
    <div className="flex max-h-[min(32rem,58vh)] min-h-0 flex-col gap-3 overflow-y-auto pr-1">
      {unmapped.map(([group, rows]) => (
        <UnmappedGroup
          key={group}
          group={group}
          rows={rows}
          sites={sites}
          target={groupTargets[group] ?? null}
          onTarget={(target) => onGroupTarget(group, target)}
        />
      ))}
      {updates.length > 0 ? (
        <DuplicateList rows={updates} selected={selected} allIds={ids} onSelected={onSelected} />
      ) : null}
      {disabled.length > 0 ? (
        <PreviewSection title="Not available to the bot">
          {disabled.map((row, index) => (
            <PreviewItem
              key={rowKey(row, index)}
              title={row.shortcut ? `#${row.shortcut}` : "Canned response"}
              detail={row.disable_reason || "Staff only."}
              excerpt={row.excerpt}
            />
          ))}
        </PreviewSection>
      ) : null}
      {creates.length > 0 ? (
        <PreviewSection title={`${creates.length} new responses`}>
          {creates.map((row, index) => (
            <PreviewItem
              key={rowKey(row, index)}
              title={row.shortcut ? `#${row.shortcut}` : "Canned response"}
              detail={row.group_name || "Ready to import."}
              excerpt={row.excerpt}
            />
          ))}
        </PreviewSection>
      ) : null}
      {unchanged.length > 0 ? (
        <p className="text-mute text-xs">{unchanged.length} already in the library, no changes.</p>
      ) : null}
      {skipped.length > 0 ? (
        <PreviewSection title="Could not import">
          {skipped.map((row, index) => (
            <PreviewItem
              key={rowKey(row, index)}
              title={row.shortcut ? `#${row.shortcut}` : "Row"}
              detail={row.reason || "Skipped."}
              excerpt={row.excerpt}
            />
          ))}
        </PreviewSection>
      ) : null}
    </div>
  )
}

const unmappedHeading = (group: number, rows: PreviewRow[]) => {
  if (rows[0]?.reason) return rows[0].reason
  const name = rows[0]?.group_name
  if (name) return `The LiveChat group ${group} is ${name}, which is not a SupportChat site.`
  return `The LiveChat group ${group} is not a SupportChat site.`
}

const UnmappedGroup = ({
  group,
  rows,
  sites,
  target,
  onTarget,
}: {
  group: number
  rows: PreviewRow[]
  sites: SiteOption[]
  target: GroupTarget | null
  onTarget: (target: GroupTarget) => void
}) => {
  const name = rows[0]?.group_name
  const selectId = `import-group-${group}-site`
  const discarded = target === "discard"
  const selectValue = discarded || target == null ? null : target
  return (
    <section className="border-line bg-ice rounded-[8px] border p-3">
      <p className="text-navy text-sm font-semibold">{unmappedHeading(group, rows)}</p>
      <p className="text-mute mt-1 text-xs">Add these to a website we host, or discard them.</p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
        <label
          htmlFor={selectId}
          className="text-ink flex min-w-0 flex-1 flex-col gap-1.5 text-xs font-medium"
        >
          Add {name || `group ${group}`} responses to
          <CannedResponseSelect
            id={selectId}
            value={selectValue}
            onValueChange={(value) => {
              if (value) onTarget(value)
            }}
            items={scopeOptions(sites)}
            label={`Add ${name || `group ${group}`} responses to`}
          />
        </label>
        <Button type="button" variant="outline" onClick={() => onTarget("discard")}>
          Discard {name || `group ${group}`} responses
        </Button>
      </div>
      {discarded ? (
        <p className="text-mute mt-2 text-xs">These responses will not be imported.</p>
      ) : null}
      <ul className="divide-line border-line bg-paper mt-3 max-h-40 divide-y overflow-y-auto rounded-[8px] border">
        {rows.map((row, index) => (
          <li key={rowKey(row, index)} className="px-3 py-2">
            <p className="text-ink text-sm font-medium">
              {row.shortcut ? `#${row.shortcut}` : "Canned response"}
            </p>
            <p className="text-mute mt-0.5 text-xs">{row.excerpt}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

const DuplicateList = ({
  rows,
  selected,
  allIds,
  onSelected,
}: {
  rows: PreviewRow[]
  selected: Set<number>
  allIds: number[]
  onSelected: (next: Set<number>) => void
}) => (
  <section className="border-line rounded-[8px] border">
    <div className="border-line flex items-center justify-between gap-2 border-b px-3 py-2">
      <p className="text-navy text-sm font-semibold">Already in the library</p>
      <div className="flex gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={() => onSelected(new Set(allIds))}>
          Select all
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => onSelected(new Set())}>
          Select none
        </Button>
      </div>
    </div>
    <p className="text-mute px-3 pt-2 text-xs">
      Update selected responses. Unchecked rows keep the wording already in SupportChat.
    </p>
    <ul className="divide-line divide-y text-sm">
      {rows.map((row, index) => {
        const id = row.livechat_id
        if (id == null) return null
        const checkboxId = `import-update-${id}`
        return (
          <li key={rowKey(row, index)} className="flex items-start gap-3 px-3 py-2">
            <input
              id={checkboxId}
              type="checkbox"
              checked={selected.has(id)}
              onChange={(event) => {
                const next = new Set(selected)
                if (event.target.checked) next.add(id)
                else next.delete(id)
                onSelected(next)
              }}
              aria-label={`Update #${row.shortcut || id}`}
              className="border-line text-ember focus-visible:ring-steel mt-0.5 size-4 rounded-sm"
            />
            <label htmlFor={checkboxId} className="min-w-0">
              <span className="text-ink block text-sm font-medium">#{row.shortcut}</span>
              <span className="text-mute mt-0.5 block text-xs">{row.excerpt}</span>
            </label>
          </li>
        )
      })}
    </ul>
  </section>
)

const PreviewSection = ({ title, children }: { title: string; children: ReactNode }) => (
  <section className="border-line rounded-[8px] border">
    <div className="border-line flex items-center justify-between gap-2 border-b px-3 py-2">
      <p className="text-navy text-sm font-semibold">{title}</p>
    </div>
    <ul className="divide-line divide-y text-sm">{children}</ul>
  </section>
)

const PreviewItem = ({
  title,
  detail,
  excerpt,
}: {
  title: string
  detail: string
  excerpt: string
}) => (
  <li className="px-3 py-2">
    <p className="text-ink font-medium">{title}</p>
    <p className="text-mute mt-0.5 text-xs">{detail}</p>
    {excerpt ? <p className="text-ink mt-1 text-xs">{excerpt}</p> : null}
  </li>
)
