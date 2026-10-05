/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-new-object-as-prop, react-perf/jsx-no-new-array-as-prop, react/no-array-index-key -- Preview controls close over row and group state. */

import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"

import {
  rowKey,
  isHardSkip,
  livechatGroupName,
  livechatGroupWebsite,
  groupedImportGroups,
  updateIds,
  unmappedGroupLabel,
  type PreviewRow,
  type PreviewPayload,
  type SiteOption,
  type GroupTarget,
} from "./canned-import-state"
import { CannedResponseSelect, scopeOptions } from "./canned-response-select"

// oxlint-disable-next-line eslint/max-lines-per-function -- Grouped preview sections stay together for one reviewable import.
export const PreviewBody = ({
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
