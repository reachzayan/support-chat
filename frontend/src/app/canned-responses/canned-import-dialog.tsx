/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-array-as-prop, react-perf/jsx-no-new-object-as-prop, react/no-array-index-key -- Dialog callbacks, live pixel size, and Base UI render props use import state. */

import {
  useEffect,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react"

import { staffUpload } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Spinner } from "@/components/ui/spinner"

import { CannedResponseSelect, scopeOptions } from "./canned-response-select"

const IMPORT_DIALOG_DEFAULT = { width: 768, height: 720 }
const IMPORT_DIALOG_MIN = { width: 520, height: 440 }
const IMPORT_DIALOG_PAD = 32
const IMPORT_DIALOG_ASPECT = IMPORT_DIALOG_DEFAULT.width / IMPORT_DIALOG_DEFAULT.height

const clampDialogSize = (width: number) => {
  const maxWidth = Math.max(IMPORT_DIALOG_MIN.width, window.innerWidth - IMPORT_DIALOG_PAD)
  const maxHeight = Math.max(IMPORT_DIALOG_MIN.height, window.innerHeight - IMPORT_DIALOG_PAD)
  let nextWidth = width
  let nextHeight = nextWidth / IMPORT_DIALOG_ASPECT

  if (nextWidth > maxWidth) {
    nextWidth = maxWidth
    nextHeight = nextWidth / IMPORT_DIALOG_ASPECT
  }
  if (nextHeight > maxHeight) {
    nextHeight = maxHeight
    nextWidth = nextHeight * IMPORT_DIALOG_ASPECT
  }
  if (nextWidth < IMPORT_DIALOG_MIN.width) {
    nextWidth = IMPORT_DIALOG_MIN.width
    nextHeight = nextWidth / IMPORT_DIALOG_ASPECT
  }
  if (nextHeight < IMPORT_DIALOG_MIN.height) {
    nextHeight = IMPORT_DIALOG_MIN.height
    nextWidth = nextHeight * IMPORT_DIALOG_ASPECT
  }
  if (nextWidth > maxWidth) {
    nextWidth = maxWidth
    nextHeight = nextWidth / IMPORT_DIALOG_ASPECT
  }
  if (nextHeight > maxHeight) {
    nextHeight = maxHeight
    nextWidth = nextHeight * IMPORT_DIALOG_ASPECT
  }

  return {
    width: Math.round(nextWidth),
    height: Math.round(nextHeight),
  }
}

const useImportDialogSize = () => {
  const [size, setSize] = useState(IMPORT_DIALOG_DEFAULT)
  useEffect(() => {
    const handleResize = () => setSize((current) => clampDialogSize(current.width))
    handleResize()
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])
  const handlePointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return
    event.preventDefault()
    const handle = event.currentTarget
    const pointerId = event.pointerId
    if (typeof handle.setPointerCapture === "function") {
      handle.setPointerCapture(pointerId)
    }
    const startX = event.clientX
    const startY = event.clientY
    const startWidth = size.width
    const startHeight = size.height
    const onMove = (move: globalThis.PointerEvent) => {
      const scale =
        ((startWidth + (move.clientX - startX)) / startWidth +
          (startHeight + (move.clientY - startY)) / startHeight) /
        2
      setSize(clampDialogSize(startWidth * scale))
    }
    const release = () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", release)
      window.removeEventListener("pointercancel", release)
      if (
        typeof handle.hasPointerCapture === "function" &&
        handle.hasPointerCapture(pointerId) &&
        typeof handle.releasePointerCapture === "function"
      ) {
        handle.releasePointerCapture(pointerId)
      }
    }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", release)
    window.addEventListener("pointercancel", release)
  }
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const step = event.shiftKey ? 40 : 16
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault()
      setSize((current) => clampDialogSize(current.width + step))
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault()
      setSize((current) => clampDialogSize(current.width - step))
    }
  }
  return {
    size,
    resetSize: () => setSize(clampDialogSize(IMPORT_DIALOG_DEFAULT.width)),
    handlePointerDown,
    handleKeyDown,
  }
}

type PreviewRow = {
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

type PreviewPayload = {
  created: number
  updated: number
  skipped: number
  rows: PreviewRow[]
}

type SiteOption = { id: string; name: string }
type GroupTarget = string | "discard"

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

const rowKey = (row: PreviewRow, index: number) => `${row.livechat_id ?? "row"}-${index}`

const isUnmappedSiteSkip = (row: PreviewRow) =>
  row.action === "skip" &&
  row.group != null &&
  /not a SupportChat (site|website)/i.test(row.reason || "")

const isMappableRow = (row: PreviewRow) =>
  row.group != null && (row.action !== "skip" || isUnmappedSiteSkip(row))

const isHardSkip = (row: PreviewRow) => row.action === "skip" && !isUnmappedSiteSkip(row)

const livechatGroupName = (group: number, rows: PreviewRow[]) =>
  rows[0]?.group_name || LIVECHAT_GROUPS[group]?.name || `group ${group}`

const livechatGroupWebsite = (group: number, rows: PreviewRow[]) =>
  rows[0]?.livechat_website || LIVECHAT_GROUPS[group]?.website || null

const groupedImportGroups = (rows: PreviewRow[]) => {
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

const unmappedGroupLabel = (group: number, rows: PreviewRow[]) => {
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

const ImportFilePicker = ({
  file,
  compact,
  onFile,
}: {
  file: File | null
  compact: boolean
  onFile: (event: ChangeEvent<HTMLInputElement>) => void
}) => (
  <label
    className={`text-ink flex cursor-pointer flex-col items-center justify-center gap-2 px-4 text-center text-sm font-medium ${
      compact ? "py-4" : "min-h-0 flex-1 py-10"
    }`}
  >
    <span>CSV file</span>
    <input
      type="file"
      accept=".csv,text/csv"
      onChange={onFile}
      aria-label="LiveChat canned responses CSV"
      className="peer sr-only"
    />
    <span className="border-line bg-paper text-navy peer-focus-visible:ring-steel rounded-[8px] border px-4 py-1.5 text-xs font-bold peer-focus-visible:ring-2">
      {file ? "Choose a different file" : "Choose file"}
    </span>
    <span className="text-mute max-w-full truncate text-xs font-normal">
      {file ? file.name : "No file chosen"}
    </span>
  </label>
)

const ImportDialogActions = ({
  previewReady,
  canImport,
  busy,
  hasFile,
  onClose,
  onPreview,
  onImport,
}: {
  previewReady: boolean
  canImport: boolean
  busy: boolean
  hasFile: boolean
  onClose: () => void
  onPreview: () => void
  onImport: () => void
}) => (
  <DialogFooter className="relative flex-row items-center justify-end gap-2 pe-11">
    <Button type="button" variant="outline" onClick={onClose}>
      Cancel
    </Button>
    {previewReady ? (
      <Button variant="default" disabled={!canImport} onClick={onImport}>
        {busy ? <Spinner data-icon="inline-start" /> : null}
        {busy ? "Importing…" : "Import responses"}
      </Button>
    ) : (
      <Button variant="default" disabled={!hasFile || busy} onClick={onPreview}>
        {busy ? <Spinner data-icon="inline-start" /> : null}
        {busy ? "Reading…" : "Preview"}
      </Button>
    )}
  </DialogFooter>
)

const ImportResizeHandle = ({
  onPointerDown,
  onKeyDown,
  onReset,
}: {
  onPointerDown: (event: PointerEvent<HTMLButtonElement>) => void
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void
  onReset: () => void
}) => (
  <button
    type="button"
    aria-label="Resize dialog"
    title="Drag to resize. Aspect ratio stays locked. Arrow keys adjust. Double-click resets."
    onPointerDown={onPointerDown}
    onKeyDown={onKeyDown}
    onDoubleClick={onReset}
    className="text-mute hover:text-ink focus-visible:text-steel absolute right-1.5 bottom-1.5 z-30 grid size-6 cursor-se-resize touch-none place-items-center rounded-none bg-transparent transition-colors duration-150 outline-none"
  >
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className="size-4 stroke-current"
      fill="none"
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <path d="M14 4 L4 14" />
      <path d="M14 9 L9 14" />
    </svg>
  </button>
)

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
  const resize = useImportDialogSize()
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) dialog.handleClose()
      }}
    >
      <DialogContent
        className="h-auto max-h-none w-auto max-w-none"
        style={{ width: resize.size.width, height: resize.size.height }}
      >
        <DialogHeader>
          <DialogTitle>Import LiveChat canned responses</DialogTitle>
          <DialogDescription>
            Choose a LiveChat canned responses CSV. Preview the rows, map each LiveChat website to
            one we host, then import them into this library.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 scrollbar-gutter-stable flex-col gap-3 overflow-y-auto px-5 py-3 pr-4">
          <ImportFilePicker
            file={dialog.file}
            compact={!!dialog.preview}
            onFile={dialog.handleFile}
          />
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
        </div>
        <ImportDialogActions
          previewReady={!!dialog.preview}
          canImport={dialog.canImport}
          busy={dialog.busy}
          hasFile={!!dialog.file}
          onClose={dialog.handleClose}
          onPreview={() => void dialog.handlePreview()}
          onImport={() => void dialog.handleImport()}
        />
        <ImportResizeHandle
          onPointerDown={resize.handlePointerDown}
          onKeyDown={resize.handleKeyDown}
          onReset={resize.resetSize}
        />
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
  const updates = preview.rows.filter((row) => row.action === "update")
  const unchanged = preview.rows.filter((row) => row.action === "unchanged")
  const skipped = preview.rows.filter(isHardSkip)
  const groups = groupedImportGroups(preview.rows)
  const ids = updateIds(preview.rows)
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {groups.map(([group, rows]) => (
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

const groupHeading = (group: number, rows: PreviewRow[]) => {
  const name = livechatGroupName(group, rows)
  return `LiveChat group ${group} · ${name}`
}

const AgentDisabledPill = () => (
  <span className="bg-ice-2 text-mute inline-flex shrink-0 rounded-[8px] px-1.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase">
    Agent Disabled
  </span>
)

const GroupMapCopy = ({ rows }: { rows: PreviewRow[] }) => (
  <ul className="divide-line border-line bg-paper mt-3 max-h-72 divide-y overflow-y-auto rounded-[8px] border">
    {rows.map((row, index) => (
      <li key={rowKey(row, index)} className="px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-ink text-sm font-medium">
            {row.shortcut ? `#${row.shortcut}` : "Canned response"}
          </p>
          {row.bot_eligible ? null : <AgentDisabledPill />}
        </div>
        {row.excerpt ? <p className="text-mute mt-0.5 text-xs">{row.excerpt}</p> : null}
      </li>
    ))}
  </ul>
)

const GroupMapTarget = ({
  group,
  name,
  selectValue,
  onTarget,
  sites,
}: {
  group: number
  name: string
  selectValue: string | null
  onTarget: (target: GroupTarget) => void
  sites: SiteOption[]
}) => {
  const selectId = `import-group-${group}-site`
  return (
    <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
      <label
        htmlFor={selectId}
        className="text-ink flex min-w-0 flex-1 flex-col gap-1.5 text-xs font-medium"
      >
        Add {name} responses to
        <CannedResponseSelect
          id={selectId}
          value={selectValue}
          onValueChange={(value) => {
            if (value) onTarget(value)
          }}
          items={scopeOptions(sites)}
          label={`Add ${name} responses to`}
        />
      </label>
      <Button type="button" variant="outline" onClick={() => onTarget("discard")}>
        Discard {name} responses
      </Button>
    </div>
  )
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
  const name = livechatGroupName(group, rows)
  const website = livechatGroupWebsite(group, rows)
  const discarded = target === "discard"
  const selectValue = discarded || target == null ? null : target
  return (
    <section className="border-line bg-ice rounded-[8px] border p-3">
      <p className="text-navy text-sm font-semibold">{groupHeading(group, rows)}</p>
      {website ? <p className="text-mute mt-0.5 font-mono text-xs">{website}</p> : null}
      <p className="text-mute mt-1 text-xs">Add these to a website we host, or discard them.</p>
      <GroupMapTarget
        group={group}
        name={name}
        selectValue={selectValue}
        onTarget={onTarget}
        sites={sites}
      />
      {target == null ? (
        <p className="text-ember mt-2 text-xs" role="alert">
          {unmappedGroupLabel(group, rows)}
        </p>
      ) : null}
      {discarded ? (
        <p className="text-mute mt-2 text-xs">These responses will not be imported.</p>
      ) : null}
      <GroupMapCopy rows={rows} />
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
