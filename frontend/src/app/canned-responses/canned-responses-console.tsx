"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-array-as-prop, react-perf/jsx-no-new-function-as-prop, jsx-a11y/label-has-associated-control, unicorn/consistent-function-scoping, eslint/complexity -- Base UI render props and controlled form handlers need the current response state; native labels wrap the controls but the custom Select trigger is not statically recognized, and each mutation keeps its error/recovery branch adjacent to its optimistic update. */

import { Pencil, Plus, Search, Trash2 } from "lucide-react"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
} from "react"

import { staffRead, staffWrite, type SiteRecord } from "@/components/admin/staff-api"
import { StaffHeader } from "@/components/admin/staff-nav"
import {
  AlertDialog,
  AlertDialogClose,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { FieldError } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"

type CannedReplyRecord = {
  id: string
  site_id: string | null
  shortcut: string
  body: string
  enabled: boolean
  created_at: string
  updated_at: string
}

type Scope = "general" | string
type StatusFilter = "all" | "enabled" | "disabled"
type FormState = {
  id: string | null
  siteId: string | null
  shortcut: string
  body: string
  enabled: boolean
}

const PAGE_SIZE = 50

const initialScope = (): Scope => {
  if (typeof window === "undefined") {
    return "general"
  }
  return new URLSearchParams(window.location.search).get("scope") ?? "general"
}

const initialStatus = (): StatusFilter => {
  if (typeof window === "undefined") {
    return "all"
  }
  const value = new URLSearchParams(window.location.search).get("status")
  return value === "enabled" || value === "disabled" ? value : "all"
}

const initialPage = () => {
  if (typeof window === "undefined") {
    return 1
  }
  const value = Number(new URLSearchParams(window.location.search).get("page"))
  return Number.isSafeInteger(value) && value > 0 ? value : 1
}

const errorMessage = async (response: Response) => {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail || "The response could not be saved. Try again."
  } catch {
    return "The response could not be saved. Try again."
  }
}

const blankForm = (scope: Scope): FormState => ({
  id: null,
  siteId: scope === "general" ? null : scope,
  shortcut: "",
  body: "",
  enabled: true,
})

const formSnapshot = (form: FormState) => JSON.stringify(form)

const scopeLabel = (scope: Scope, sites: SiteRecord[]) =>
  scope === "general"
    ? "General — all websites"
    : (sites.find((site) => site.id === scope)?.name ?? "")

const statusClass = (enabled: boolean) =>
  enabled
    ? "bg-[#E8F5EE] text-[#247A4D] dark:bg-[#163627] dark:text-[#8DDEAE]"
    : "bg-ice-2 text-mute dark:bg-white/10 dark:text-white/60"

const formatDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(value),
  )

// oxlint-disable-next-line eslint/max-lines-per-function -- The route owns one cohesive library view and its local mutation state.
export const CannedResponsesConsole = () => {
  const [records, setRecords] = useState<CannedReplyRecord[] | null>(null)
  const [sites, setSites] = useState<SiteRecord[]>([])
  const [loadError, setLoadError] = useState("")
  const [showLoading, setShowLoading] = useState(false)
  const [scope, setScope] = useState<Scope>(initialScope)
  const [query, setQuery] = useState(() =>
    typeof window === "undefined"
      ? ""
      : (new URLSearchParams(window.location.search).get("q") ?? ""),
  )
  const [status, setStatus] = useState<StatusFilter>(initialStatus)
  const [page, setPage] = useState(initialPage)
  const [form, setForm] = useState<FormState | null>(null)
  const [initialForm, setInitialForm] = useState("")
  const [formError, setFormError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [discardOpen, setDiscardOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<CannedReplyRecord | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({})
  const [pendingIds, setPendingIds] = useState<string[]>([])
  const [announcement, setAnnouncement] = useState("")
  const shortcutRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoadError("")
    setRecords(null)
    const delay = window.setTimeout(() => setShowLoading(true), 400)
    try {
      const [libraryResponse, sitesResponse] = await Promise.all([
        staffRead("/api/canned-replies/library"),
        staffRead("/api/sites"),
      ])
      if (!libraryResponse.ok || !sitesResponse.ok) {
        setLoadError("Canned responses could not be loaded. Check your connection and try again.")
        return
      }
      const library = (await libraryResponse.json()) as { items: CannedReplyRecord[] }
      const sitePayload = (await sitesResponse.json()) as { items: SiteRecord[] }
      setRecords(library.items)
      setSites(sitePayload.items)
    } catch {
      setLoadError("Canned responses could not be loaded. Check your connection and try again.")
    } finally {
      window.clearTimeout(delay)
      setShowLoading(false)
    }
  }, [])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Start the initial asynchronous library request after the client mounts.
    void load()
  }, [load])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const nextStatus = params.get("status")
    const nextPage = Number(params.get("page"))
    // oxlint-disable-next-line react/set-state-in-effect -- URL query state is client-only because this screen is rendered inside the authenticated shell.
    setScope(params.get("scope") ?? "general")
    setQuery(params.get("q") ?? "")
    setStatus(nextStatus === "enabled" || nextStatus === "disabled" ? nextStatus : "all")
    setPage(Number.isSafeInteger(nextPage) && nextPage > 0 ? nextPage : 1)
  }, [])

  const updateUrl = useCallback(
    (next: Partial<{ scope: Scope; q: string; status: StatusFilter; page: number }>) => {
      const params = new URLSearchParams(window.location.search)
      const merged = { scope, q: query, status, page, ...next }
      if (merged.scope === "general") params.delete("scope")
      else params.set("scope", merged.scope)
      if (merged.q) params.set("q", merged.q)
      else params.delete("q")
      if (merged.status === "all") params.delete("status")
      else params.set("status", merged.status)
      if (merged.page === 1) params.delete("page")
      else params.set("page", String(merged.page))
      const suffix = params.toString()
      window.history.replaceState(null, "", `/admin/canned-responses${suffix ? `?${suffix}` : ""}`)
    },
    [page, query, scope, status],
  )

  const selectScope = useCallback(
    (next: string | null) => {
      const value = next || "general"
      setScope(value)
      setPage(1)
      updateUrl({ scope: value, page: 1 })
    },
    [updateUrl],
  )

  const updateQuery = useCallback(
    (value: string) => {
      setQuery(value)
      setPage(1)
      updateUrl({ q: value, page: 1 })
    },
    [updateUrl],
  )

  const updateStatus = useCallback(
    (value: string | null) => {
      const next = value === "enabled" || value === "disabled" ? value : "all"
      setStatus(next)
      setPage(1)
      updateUrl({ status: next, page: 1 })
    },
    [updateUrl],
  )

  const scoped = useMemo(
    () =>
      (records ?? []).filter((row) =>
        scope === "general" ? row.site_id === null : row.site_id === scope,
      ),
    [records, scope],
  )
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return scoped.filter((row) => {
      const matchesQuery = !needle || `${row.shortcut} ${row.body}`.toLowerCase().includes(needle)
      return matchesQuery && (status === "all" || (status === "enabled") === row.enabled)
    })
  }, [query, scoped, status])
  const visible = useMemo(
    () => filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filtered, page],
  )
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const summary = useMemo(() => {
    if (scope === "general") {
      return `${scoped.length} responses · ${scoped.filter((row) => row.enabled).length} enabled`
    }
    const general = (records ?? []).filter((row) => row.site_id === null && row.enabled)
    const overrides = new Set(scoped.map((row) => row.shortcut))
    const inherited = general.filter((row) => !overrides.has(row.shortcut))
    const effective = scoped.filter((row) => row.enabled).length + inherited.length
    return `${scoped.length} website-specific · ${inherited.length} inherited · ${effective} effective enabled`
  }, [records, scope, scoped])

  const openCreate = useCallback(() => {
    const next = blankForm(scope)
    setForm(next)
    setInitialForm(formSnapshot(next))
    setFormError("")
  }, [scope])

  const openEdit = useCallback((record: CannedReplyRecord) => {
    const next = {
      id: record.id,
      siteId: record.site_id,
      shortcut: record.shortcut,
      body: record.body,
      enabled: record.enabled,
    }
    setForm(next)
    setInitialForm(formSnapshot(next))
    setFormError("")
  }, [])

  const requestClose = useCallback(() => {
    if (form && formSnapshot(form) !== initialForm) {
      setDiscardOpen(true)
      return
    }
    setForm(null)
  }, [form, initialForm])

  const saveForm = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      if (!form || submitting) return
      setSubmitting(true)
      setFormError("")
      const payload = {
        site_id: form.siteId,
        shortcut: form.shortcut,
        body: form.body,
        enabled: form.enabled,
      }
      const path = form.id ? `/api/canned-replies/${form.id}` : "/api/canned-replies"
      const method = form.id ? "PATCH" : "POST"
      try {
        const response = await staffWrite(path, method, payload)
        if (!response.ok) {
          const message =
            response.status === 409
              ? `#${form.shortcut.trim().replace(/^#/, "").toLowerCase()} already exists in ${scopeLabel(form.siteId ?? "general", sites)}.`
              : await errorMessage(response)
          setFormError(message)
          if (response.status === 409) shortcutRef.current?.focus()
          return
        }
        const saved = (await response.json()) as CannedReplyRecord
        setRecords((current) => {
          if (current === null) return current
          return form.id
            ? current.map((row) => (row.id === saved.id ? saved : row))
            : [...current, saved]
        })
        setForm(null)
        setAnnouncement(form.id ? "Canned response updated." : "Canned response created.")
      } catch {
        setFormError("The response could not be saved. Try again.")
      } finally {
        setSubmitting(false)
      }
    },
    [form, sites, submitting],
  )

  const toggle = useCallback(
    async (record: CannedReplyRecord) => {
      if (pendingIds.includes(record.id)) return
      const nextEnabled = !record.enabled
      setPendingIds((current) => [...current, record.id])
      setRowErrors((current) => ({ ...current, [record.id]: "" }))
      setRecords(
        (current) =>
          current?.map((row) => (row.id === record.id ? { ...row, enabled: nextEnabled } : row)) ??
          null,
      )
      try {
        const response = await staffWrite(`/api/canned-replies/${record.id}`, "PATCH", {
          enabled: nextEnabled,
        })
        if (!response.ok) throw new Error(await errorMessage(response))
        const saved = (await response.json()) as CannedReplyRecord
        setRecords((current) => current?.map((row) => (row.id === record.id ? saved : row)) ?? null)
      } catch (error) {
        setRecords(
          (current) => current?.map((row) => (row.id === record.id ? record : row)) ?? null,
        )
        setRowErrors((current) => ({
          ...current,
          [record.id]: error instanceof Error ? error.message : "The state could not be changed.",
        }))
      } finally {
        setPendingIds((current) => current.filter((id) => id !== record.id))
      }
    },
    [pendingIds],
  )

  const deleteResponse = useCallback(async () => {
    if (!deleteTarget || deleting) return
    setDeleting(true)
    try {
      const response = await staffWrite(
        `/api/canned-replies/${deleteTarget.id}`,
        "DELETE",
        undefined,
      )
      if (!response.ok) {
        const message = await errorMessage(response)
        setRowErrors((current) => ({ ...current, [deleteTarget.id]: message }))
        return
      }
      setRecords((current) => current?.filter((row) => row.id !== deleteTarget.id) ?? null)
      setDeleteTarget(null)
      setAnnouncement("Canned response removed.")
    } catch {
      setRowErrors((current) => ({
        ...current,
        [deleteTarget.id]: "The response could not be removed. Try again.",
      }))
    } finally {
      setDeleting(false)
    }
  }, [deleteTarget, deleting])

  if (loadError) {
    return (
      <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col">
        <StaffHeader
          title="Canned responses"
          description="Reuse approved specialist wording across chats."
        />
        <main id="main-content" className="flex flex-1 items-center justify-center p-6">
          <div className="border-line bg-paper w-full max-w-md rounded-xl border p-6 text-center">
            <p className="text-navy heading text-base">Canned responses could not be loaded</p>
            <p className="text-mute mt-2 text-sm">Check your connection and try again.</p>
            <Button className="bg-ember hover:bg-ember/90 mt-5" onClick={() => void load()}>
              Retry
            </Button>
          </div>
        </main>
      </div>
    )
  }

  if (records === null) {
    return (
      <div className="view-transition-enter bg-ice min-h-0 min-w-0 flex-1 overflow-y-auto">
        <StaffHeader
          title="Canned responses"
          description="Reuse approved specialist wording across chats."
        />
        {showLoading ? <CannedResponsesSkeleton /> : null}
      </div>
    )
  }

  return (
    <div className="view-transition-enter bg-ice min-h-0 min-w-0 flex-1 overflow-y-auto">
      <StaffHeader
        title="Canned responses"
        description="Reuse approved specialist wording across chats."
        action={
          <Button className="bg-ember hover:bg-ember/90" onClick={openCreate}>
            <Plus aria-hidden="true" /> Add response
          </Button>
        }
      />
      <main
        id="main-content"
        className="flex w-full min-w-0 flex-col gap-4 px-5 py-6 lg:px-8 lg:py-8"
      >
        <section className="border-line bg-paper rounded-xl border p-4 sm:p-5">
          <div className="grid gap-3 lg:grid-cols-[minmax(15rem,0.8fr)_minmax(18rem,1.2fr)_10rem]">
            <div className="text-ink flex flex-col gap-1.5 text-xs font-medium">
              <span>Scope</span>
              <Select
                value={scope}
                onValueChange={selectScope}
                items={[
                  { value: "general", label: "General — all websites" },
                  ...sites.map((site) => ({ value: site.id, label: site.name })),
                ]}
              >
                <SelectTrigger
                  aria-label="Scope"
                  className="border-line bg-ice h-10 w-full rounded-[8px]"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="start" alignItemWithTrigger={false}>
                  <SelectGroup>
                    <SelectItem value="general">General — all websites</SelectItem>
                    {sites.map((site) => (
                      <SelectItem key={site.id} value={site.id}>
                        {site.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <div className="text-ink flex flex-col gap-1.5 text-xs font-medium">
              <span>Search</span>
              <span className="border-line bg-ice flex h-10 items-center gap-2 rounded-[8px] border px-3">
                <Search aria-hidden="true" className="text-mute size-4" />
                <Input
                  aria-label="Search canned responses"
                  value={query}
                  onChange={(event) => updateQuery(event.target.value)}
                  placeholder="# or message…"
                  className="h-auto border-0 bg-transparent p-0 shadow-none focus-visible:ring-0"
                />
              </span>
            </div>
            <div className="text-ink flex flex-col gap-1.5 text-xs font-medium">
              <span>Status</span>
              <Select
                value={status}
                onValueChange={updateStatus}
                items={[
                  { value: "all", label: "All" },
                  { value: "enabled", label: "Enabled" },
                  { value: "disabled", label: "Disabled" },
                ]}
              >
                <SelectTrigger
                  aria-label="Status"
                  className="border-line bg-ice h-10 w-full rounded-[8px]"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="start" alignItemWithTrigger={false}>
                  <SelectGroup>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="enabled">Enabled</SelectItem>
                    <SelectItem value="disabled">Disabled</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          </div>
          <p className="text-mute mt-4 text-xs" aria-live="polite">
            {summary}
          </p>
          {scope !== "general" ? (
            <p className="text-mute mt-1 text-xs">
              Matching website shortcuts override General responses and remain overridden while
              disabled.
            </p>
          ) : null}
        </section>

        {visible.length === 0 ? (
          <EmptyState scope={scope} sites={sites} onAdd={openCreate} />
        ) : (
          <section className="border-line bg-paper overflow-hidden rounded-xl border">
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                <thead className="bg-ice-2 text-ink text-xs">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Shortcut</th>
                    <th className="px-5 py-3 font-semibold">Message</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold">Updated</th>
                    <th className="px-5 py-3 font-semibold">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((record) => (
                    <ResponseRow
                      key={record.id}
                      record={record}
                      scope={scope}
                      records={records}
                      pending={pendingIds.includes(record.id)}
                      error={rowErrors[record.id]}
                      onToggle={toggle}
                      onEdit={openEdit}
                      onDelete={setDeleteTarget}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="divide-line flex flex-col divide-y md:hidden">
              {visible.map((record) => (
                <ResponseCard
                  key={record.id}
                  record={record}
                  scope={scope}
                  records={records}
                  pending={pendingIds.includes(record.id)}
                  error={rowErrors[record.id]}
                  onToggle={toggle}
                  onEdit={openEdit}
                  onDelete={setDeleteTarget}
                />
              ))}
            </div>
          </section>
        )}
        {totalPages > 1 ? (
          <Pagination
            page={page}
            total={totalPages}
            onChange={(next) => {
              setPage(next)
              updateUrl({ page: next })
            }}
          />
        ) : null}
      </main>
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
      <ResponseForm
        form={form}
        sites={sites}
        formError={formError}
        submitting={submitting}
        onChange={setForm}
        onSubmit={saveForm}
        onRequestClose={requestClose}
        shortcutRef={shortcutRef}
      />
      <AlertDialog open={discardOpen} onOpenChange={setDiscardOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard changes?</AlertDialogTitle>
            <AlertDialogDescription>
              Your unsaved response changes will be lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogClose render={<Button variant="outline">Keep editing</Button>} />
            <Button
              className="bg-ember hover:bg-ember/90"
              onClick={() => {
                setDiscardOpen(false)
                setForm(null)
              }}
            >
              Discard changes
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <DeleteDialog
        target={deleteTarget}
        sites={sites}
        deleting={deleting}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => void deleteResponse()}
      />
    </div>
  )
}

const ResponseRow = ({
  record,
  scope,
  records,
  pending,
  error,
  onToggle,
  onEdit,
  onDelete,
}: ResponseItemProps) => (
  <tr className="border-line hover:bg-ice/60 border-t transition-[opacity,transform,background-color] duration-150">
    <td className="text-steel px-5 py-3 font-mono text-sm font-bold">#{record.shortcut}</td>
    <td className="max-w-md px-5 py-3">
      <p className="text-ink line-clamp-2">{record.body}</p>
      {overrideNote(record, scope, records)}
    </td>
    <td className="px-5 py-3">
      <div className="flex items-center gap-2">
        <Switch
          aria-label={`${record.enabled ? "Disable" : "Enable"} #${record.shortcut}`}
          checked={record.enabled}
          disabled={pending}
          onCheckedChange={() => void onToggle(record)}
        />
        <Badge className={statusClass(record.enabled)}>
          {record.enabled ? "Enabled" : "Disabled"}
        </Badge>
      </div>
      {error ? <RowError text={error} onRetry={() => void onToggle(record)} /> : null}
    </td>
    <td className="text-mute px-5 py-3 text-xs">{formatDate(record.updated_at)}</td>
    <td className="px-5 py-3">
      <div className="flex justify-end gap-1">
        <Button variant="ghost" size="sm" onClick={() => onEdit(record)}>
          <Pencil aria-hidden="true" /> Edit
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Remove #${record.shortcut}`}
          onClick={() => onDelete(record)}
        >
          <Trash2 aria-hidden="true" />
        </Button>
      </div>
    </td>
  </tr>
)

type ResponseItemProps = {
  record: CannedReplyRecord
  scope: Scope
  records: CannedReplyRecord[]
  pending: boolean
  error?: string
  onToggle: (record: CannedReplyRecord) => Promise<void>
  onEdit: (record: CannedReplyRecord) => void
  onDelete: (record: CannedReplyRecord) => void
}

const ResponseCard = ({
  record,
  scope,
  records,
  pending,
  error,
  onToggle,
  onEdit,
  onDelete,
}: ResponseItemProps) => (
  <article className="p-4 transition-[opacity,transform] duration-150">
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-steel font-mono text-sm font-bold">#{record.shortcut}</p>
        <p className="text-ink mt-2 line-clamp-3 text-sm leading-6">{record.body}</p>
        {overrideNote(record, scope, records)}
      </div>
      <div className="flex flex-col items-end gap-2">
        <Switch
          aria-label={`${record.enabled ? "Disable" : "Enable"} #${record.shortcut}`}
          checked={record.enabled}
          disabled={pending}
          onCheckedChange={() => void onToggle(record)}
        />
        <Badge className={statusClass(record.enabled)}>
          {record.enabled ? "Enabled" : "Disabled"}
        </Badge>
      </div>
    </div>
    <div className="mt-4 flex items-center justify-between">
      <span className="text-mute text-xs">Updated {formatDate(record.updated_at)}</span>
      <div className="flex gap-1">
        <Button variant="ghost" size="sm" onClick={() => onEdit(record)}>
          Edit
        </Button>
        <Button variant="ghost" size="sm" className="text-ember" onClick={() => onDelete(record)}>
          Remove
        </Button>
      </div>
    </div>
    {error ? <RowError text={error} onRetry={() => void onToggle(record)} /> : null}
  </article>
)

const overrideNote = (record: CannedReplyRecord, scope: Scope, records: CannedReplyRecord[]) =>
  scope !== "general" &&
  !record.enabled &&
  records.some((row) => row.site_id === null && row.shortcut === record.shortcut) ? (
    <p className="text-mute mt-1 text-xs">
      Disabled here. The General #{record.shortcut} response also remains hidden.
    </p>
  ) : null

const RowError = ({ text, onRetry }: { text: string; onRetry: () => void }) => (
  <p className="text-ember mt-2 text-xs" role="alert">
    {text}{" "}
    <button type="button" className="underline underline-offset-2" onClick={onRetry}>
      Retry
    </button>
  </p>
)

const EmptyState = ({
  scope,
  sites,
  onAdd,
}: {
  scope: Scope
  sites: SiteRecord[]
  onAdd: () => void
}) => (
  <section className="border-line bg-paper rounded-xl border p-8 text-center">
    <p className="text-navy heading text-base">
      {scope === "general" ? "No General responses yet" : "No website responses yet"}
    </p>
    <p className="text-mute mx-auto mt-2 max-w-md text-sm">
      {scope === "general"
        ? "Responses created here work across every website."
        : `General responses remain available unless this website defines the same shortcut. ${scopeLabel(scope, sites)} can have its own approved wording.`}
    </p>
    <Button className="bg-ember hover:bg-ember/90 mt-5" onClick={onAdd}>
      Add {scope === "general" ? "general" : "website"} response
    </Button>
  </section>
)

const Pagination = ({
  page,
  total,
  onChange,
}: {
  page: number
  total: number
  onChange: (page: number) => void
}) => (
  <div className="flex items-center justify-end gap-3">
    <span className="text-mute text-xs">
      Page {page} of {total}
    </span>
    <Button variant="outline" disabled={page === 1} onClick={() => onChange(page - 1)}>
      Previous
    </Button>
    <Button variant="outline" disabled={page === total} onClick={() => onChange(page + 1)}>
      Next
    </Button>
  </div>
)

const CannedResponsesSkeleton = () => (
  <main className="flex flex-col gap-4 px-5 py-6 lg:px-8 lg:py-8">
    <Skeleton className="h-28 w-full rounded-xl" />
    <Skeleton className="h-56 w-full rounded-xl" />
  </main>
)

// oxlint-disable-next-line eslint/max-lines-per-function -- Form fields, scope picker, and submit validation stay together for one reviewable edit flow.
const ResponseForm = ({
  form,
  sites,
  formError,
  submitting,
  onChange,
  onSubmit,
  onRequestClose,
  shortcutRef,
}: {
  form: FormState | null
  sites: SiteRecord[]
  formError: string
  submitting: boolean
  onChange: (next: FormState) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onRequestClose: () => void
  shortcutRef: RefObject<HTMLInputElement | null>
}) => {
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter")
      event.currentTarget.form?.requestSubmit()
  }
  return (
    <Dialog
      open={form !== null}
      onOpenChange={(open) => {
        if (!open) onRequestClose()
      }}
    >
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>{form?.id ? "Edit canned response" : "Add canned response"}</DialogTitle>
          <DialogDescription>
            Plain-text wording is inserted into the composer for staff to review before sending.
          </DialogDescription>
        </DialogHeader>
        {form ? (
          <form onSubmit={onSubmit} className="flex min-h-0 flex-1 flex-col overflow-y-auto">
            <div className="flex flex-col gap-4 px-5 py-5">
              <label className="text-ink flex flex-col gap-1.5 text-sm font-medium">
                Scope
                <Select
                  value={form.siteId ?? "general"}
                  onValueChange={(value) =>
                    onChange({ ...form, siteId: value === "general" ? null : value })
                  }
                  items={[
                    { value: "general", label: "General — all websites" },
                    ...sites.map((site) => ({ value: site.id, label: site.name })),
                  ]}
                >
                  <SelectTrigger className="border-line bg-ice h-10 w-full rounded-[8px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent align="start" alignItemWithTrigger={false}>
                    <SelectGroup>
                      <SelectItem value="general">General — all websites</SelectItem>
                      {sites.map((site) => (
                        <SelectItem key={site.id} value={site.id}>
                          {site.name}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </label>
              <label className="text-ink flex flex-col gap-1.5 text-sm font-medium">
                Shortcut
                <span className="border-line bg-ice flex h-10 items-center rounded-[8px] border px-3">
                  <span className="text-mute font-mono">#</span>
                  <input
                    ref={shortcutRef}
                    value={form.shortcut}
                    maxLength={40}
                    onChange={(event) => onChange({ ...form, shortcut: event.target.value })}
                    aria-invalid={formError.includes("shortcut") || undefined}
                    className="text-ink min-w-0 flex-1 bg-transparent p-0 font-mono text-sm outline-none focus-visible:ring-0"
                  />
                </span>
                <span className="text-mute text-xs">{form.shortcut.length}/40 characters</span>
              </label>
              <label className="text-ink flex flex-col gap-1.5 text-sm font-medium">
                Message
                <Textarea
                  value={form.body}
                  maxLength={4000}
                  onKeyDown={keyDown}
                  onChange={(event) => onChange({ ...form, body: event.target.value })}
                  aria-invalid={formError.includes("Message") || undefined}
                />
                <span className="text-mute text-xs">
                  {form.body.length}/4,000 characters · Ctrl/⌘+Enter to save
                </span>
              </label>
              <label className="border-line bg-ice text-ink flex items-center justify-between gap-3 rounded-[8px] border px-3 py-2.5 text-sm font-medium">
                <span>
                  <span className="block">Enabled</span>
                  <span className="text-mute block text-xs font-normal">
                    Available in the inbox when this scope is active.
                  </span>
                </span>
                <Switch
                  checked={form.enabled}
                  onCheckedChange={(enabled) => onChange({ ...form, enabled })}
                  aria-label="Enabled"
                />
              </label>
              <FieldError>{formError || undefined}</FieldError>
            </div>
            <DialogFooter className="flex-row justify-end">
              <Button type="button" variant="outline" onClick={onRequestClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={submitting} className="bg-ember hover:bg-ember/90">
                {submitting ? "Saving…" : form.id ? "Save changes" : "Save response"}
              </Button>
            </DialogFooter>
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

const DeleteDialog = ({
  target,
  sites,
  deleting,
  onCancel,
  onConfirm,
}: {
  target: CannedReplyRecord | null
  sites: SiteRecord[]
  deleting: boolean
  onCancel: () => void
  onConfirm: () => void
}) => (
  <AlertDialog
    open={target !== null}
    onOpenChange={(open) => {
      if (!open) onCancel()
    }}
  >
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>Remove canned response?</AlertDialogTitle>
        <AlertDialogDescription>
          {target
            ? `#${target.shortcut} in ${target.site_id === null ? "General" : scopeLabel(target.site_id, sites)} will be permanently deleted. Disabling keeps it available for later.`
            : ""}
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogClose render={<Button variant="outline">Cancel</Button>} />
        <Button variant="destructive" disabled={deleting} onClick={onConfirm}>
          {deleting ? "Removing…" : "Remove response"}
        </Button>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
)
