import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react"

import { staffRead, staffWrite, type SiteRecord } from "@/components/admin/staff-api"
import { matchesSearchQuery } from "@/lib/search"

import {
  botState,
  parseAliasesText,
  scopeLabel,
  type BotFilter,
  type CannedReplyRecord,
  type FormState,
  type Scope,
  type StatusFilter,
} from "./canned-response-model"

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

const errorMessage = async (response: Response) => {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail || "The response could not be saved. Try again."
  } catch {
    return "The response could not be saved. Try again."
  }
}

const saveError = (response: Response, form: FormState, sites: SiteRecord[]) =>
  response.status === 409
    ? `#${form.shortcut.trim().replace(/^#/, "").toLowerCase()} already exists in ${scopeLabel(form.siteId ?? "general", sites)}.`
    : errorMessage(response)

const initialBot = (): BotFilter => {
  if (typeof window === "undefined") {
    return "all"
  }
  const value = new URLSearchParams(window.location.search).get("assistant")
  return value === "available" || value === "staff" || value === "blocked" ? value : "all"
}

const blankForm = (scope: Scope): FormState => ({
  id: null,
  siteId: scope === "general" ? null : scope,
  shortcut: "",
  aliasesText: "",
  body: "",
  enabled: true,
  botEligible: true,
  followsId: null,
  handsOff: false,
})

const savedAnnouncement = (updated: boolean, saved: CannedReplyRecord) => {
  const message = updated ? "Canned response updated." : "Canned response created."
  return saved.bot_eligible && saved.bot_block_reason
    ? `${message} The assistant will not use it. ${saved.bot_block_reason}`
    : message
}

const formSnapshot = (form: FormState) => JSON.stringify(form)
// oxlint-disable-next-line eslint/max-lines-per-function -- The route owns one cohesive library view and its local mutation state.
export const useCannedResponsesState = () => {
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
  const [bot, setBot] = useState<BotFilter>(initialBot)
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
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
  const deferredQuery = useDeferredValue(query)

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
    // oxlint-disable-next-line react/set-state-in-effect -- URL query state is client-only because this screen is rendered inside the authenticated shell.
    setScope(params.get("scope") ?? "general")
    setQuery(params.get("q") ?? "")
    setStatus(nextStatus === "enabled" || nextStatus === "disabled" ? nextStatus : "all")
    setBot(initialBot())
  }, [])

  const updateUrl = useCallback(
    (next: Partial<{ scope: Scope; q: string; status: StatusFilter; assistant: BotFilter }>) => {
      const params = new URLSearchParams(window.location.search)
      const merged = { scope, q: query, status, assistant: bot, ...next }
      if (merged.scope === "general") params.delete("scope")
      else params.set("scope", merged.scope)
      if (merged.q) params.set("q", merged.q)
      else params.delete("q")
      if (merged.status === "all") params.delete("status")
      else params.set("status", merged.status)
      if (merged.assistant === "all") params.delete("assistant")
      else params.set("assistant", merged.assistant)
      params.delete("page")
      const suffix = params.toString()
      window.history.replaceState(null, "", `/admin/canned-responses${suffix ? `?${suffix}` : ""}`)
    },
    [bot, query, scope, status],
  )

  const selectScope = useCallback(
    (next: string | null) => {
      const value = next || "general"
      setScope(value)
      setVisibleCount(PAGE_SIZE)
      updateUrl({ scope: value })
    },
    [updateUrl],
  )

  const updateQuery = useCallback(
    (value: string) => {
      setQuery(value)
      setVisibleCount(PAGE_SIZE)
      updateUrl({ q: value })
    },
    [updateUrl],
  )

  const updateStatus = useCallback(
    (value: string | null) => {
      const next = value === "enabled" || value === "disabled" ? value : "all"
      setStatus(next)
      setVisibleCount(PAGE_SIZE)
      updateUrl({ status: next })
    },
    [updateUrl],
  )

  const updateBot = useCallback(
    (value: string | null) => {
      const next = value === "available" || value === "staff" || value === "blocked" ? value : "all"
      setBot(next)
      setVisibleCount(PAGE_SIZE)
      updateUrl({ assistant: next })
    },
    [updateUrl],
  )

  const clearSearchFilters = useCallback(() => {
    setQuery("")
    setStatus("all")
    setBot("all")
    setVisibleCount(PAGE_SIZE)
    updateUrl({ q: "", status: "all", assistant: "all" })
  }, [updateUrl])

  const scoped = useMemo(
    () =>
      (records ?? []).filter((row) =>
        scope === "general" ? row.site_id === null : row.site_id === scope,
      ),
    [records, scope],
  )
  const filtered = useMemo(() => {
    return scoped.filter((row) => {
      const matchesQuery = matchesSearchQuery(
        [row.shortcut, ...(row.aliases ?? []), row.body],
        deferredQuery,
      )
      const matchesStatus = status === "all" || (status === "enabled") === row.enabled
      return matchesQuery && matchesStatus && (bot === "all" || botState(row) === bot)
    })
  }, [bot, deferredQuery, scoped, status])
  const visible = useMemo(() => filtered.slice(0, visibleCount), [filtered, visibleCount])
  const hasMore = visible.length < filtered.length
  const loadMore = useCallback(() => {
    setVisibleCount((count) => count + PAGE_SIZE)
  }, [])
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
      aliasesText: (record.aliases ?? []).join(", "),
      body: record.body,
      enabled: record.enabled,
      botEligible: record.bot_eligible,
      followsId: record.follows_id,
      handsOff: record.hands_off,
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
      const shortcut = form.shortcut.trim().replace(/^#/, "").toLowerCase()
      const payload = {
        site_id: form.siteId,
        shortcut: form.shortcut,
        aliases: parseAliasesText(form.aliasesText, shortcut),
        body: form.body,
        enabled: form.enabled,
        bot_eligible: form.botEligible,
        follows_id: form.followsId,
        hands_off: form.handsOff,
      }
      const path = form.id ? `/api/canned-replies/${form.id}` : "/api/canned-replies"
      const method = form.id ? "PATCH" : "POST"
      try {
        const response = await staffWrite(path, method, payload)
        if (!response.ok) {
          const message = await saveError(response, form, sites)
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
        setAnnouncement(savedAnnouncement(Boolean(form.id), saved))
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
  return {
    records,
    sites,
    loadError,
    showLoading,
    scope,
    query,
    status,
    bot,
    form,
    formError,
    submitting,
    discardOpen,
    setDiscardOpen,
    deleteTarget,
    setDeleteTarget,
    deleting,
    rowErrors,
    pendingIds,
    announcement,
    shortcutRef,
    load,
    selectScope,
    updateQuery,
    updateStatus,
    updateBot,
    clearSearchFilters,
    visible,
    hasMore,
    loadMore,
    summary,
    openCreate,
    openEdit,
    requestClose,
    saveForm,
    toggle,
    deleteResponse,
    setForm,
  }
}
