import { useCallback, useEffect, useRef, useState } from "react"

import { staffRead, staffWrite, type SiteRecord } from "@/components/admin/staff-api"
import { useSearchTarget, useOpenSearchTarget } from "@/components/search/workspace-route"

import type {
  AnswerPayload,
  GapQueue,
  GapRecord,
  GapView,
  SimilarEntries,
} from "./suggested-faq-model"

export const ALL_WEBSITES = "all"
const LOAD_ERROR = "Suggested FAQs could not be loaded. Check your connection and try again."
const DISMISS_ERROR = "This question could not be dismissed."
const REOPEN_ERROR = "This question could not be reopened."
const ANSWER_ERROR = "The answer could not be saved. Try again."
const ADMIN_ONLY = "Only admins can add knowledge text."
const CONFLICT = 409

type Announce = (message: string) => void
type RemoveGap = (gapId: string) => void
type UpdateGap = (gapId: string, patch: Partial<GapRecord>) => void
type ForGap<T> = { gapId: string; value: T }

const answerError = async (response: Response) => {
  if (response.status === 403) return ADMIN_ONLY
  try {
    const body = (await response.json()) as { detail?: unknown }
    return typeof body.detail === "string" ? body.detail : ANSWER_ERROR
  } catch {
    return ANSWER_ERROR
  }
}

const queuePath = (website: string, view: GapView) => {
  const params = new URLSearchParams()
  if (website !== ALL_WEBSITES) params.set("site_id", website)
  if (view !== "open") params.set("status", view)
  const query = params.toString()
  return query ? `/api/knowledge-gaps?${query}` : "/api/knowledge-gaps"
}

const fetchQueue = async (website: string, view: GapView) => {
  const [queueResponse, sitesResponse] = await Promise.all([
    staffRead(queuePath(website, view)),
    staffRead("/api/sites"),
  ])
  if (!queueResponse.ok || !sitesResponse.ok) return null
  return {
    queue: (await queueResponse.json()) as GapQueue,
    sites: ((await sitesResponse.json()) as { items: SiteRecord[] }).items,
  }
}

const queueSelection = (target: Readonly<Record<string, string>>) => {
  const initialWebsite = target.site ?? ALL_WEBSITES
  const initialView: GapView =
    target.view === "dismissed"
      ? "dismissed"
      : target.view === "canned" || target.view === "knowledge" || target.view === "answered"
        ? "answered"
        : "open"
  return { website: initialWebsite, view: initialView }
}

const useGapQueue = () => {
  const target = useSearchTarget()
  const { website: initialWebsite, view: initialView } = queueSelection(target)
  const [queue, setQueue] = useState<GapQueue | null>(null)
  // Which view the loaded queue belongs to, so a tab never shows another tab's cards.
  const [queueView, setQueueView] = useState<GapView>(initialView)
  const [sites, setSites] = useState<SiteRecord[]>([])
  const [website, setWebsite] = useState(initialWebsite)
  const [view, setView] = useState<GapView>(initialView)
  const [loadError, setLoadError] = useState("")
  // A slow answer for one website or tab must never overwrite the list chosen next.
  const latestLoad = useRef(0)

  const load = useCallback(async (selectedWebsite: string, selectedView: GapView) => {
    const requestId = ++latestLoad.current
    setLoadError("")
    try {
      const loaded = await fetchQueue(selectedWebsite, selectedView)
      if (requestId !== latestLoad.current) return
      if (loaded === null) {
        setLoadError(LOAD_ERROR)
        return
      }
      setQueue(loaded.queue)
      setQueueView(selectedView)
      setSites(loaded.sites)
    } catch {
      if (requestId === latestLoad.current) setLoadError(LOAD_ERROR)
    }
  }, [])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Start the initial asynchronous queue request after the client mounts.
    void load(initialWebsite, initialView)
  }, [load, initialWebsite, initialView])

  const updateItems = useCallback((change: (items: GapRecord[]) => GapRecord[]) => {
    setQueue((current) => (current ? { ...current, items: change(current.items) } : current))
  }, [])

  const removeGap = useCallback<RemoveGap>(
    (gapId) => updateItems((items) => items.filter((item) => item.id !== gapId)),
    [updateItems],
  )

  const updateGap = useCallback<UpdateGap>(
    (gapId, patch) =>
      updateItems((items) =>
        items.map((item) => (item.id === gapId ? { ...item, ...patch } : item)),
      ),
    [updateItems],
  )

  const selectWebsite = useCallback(
    (value: string | null) => {
      const next = value ?? ALL_WEBSITES
      setWebsite(next)
      void load(next, view)
    },
    [load, view],
  )

  const selectView = useCallback(
    (next: GapView) => {
      setView(next)
      void load(website, next)
    },
    [load, website],
  )

  const reload = useCallback(() => load(website, view), [load, view, website])

  return {
    queue: queueView === view ? queue : null,
    hasLoaded: queue !== null,
    sites,
    website,
    view,
    loadError,
    reload,
    selectWebsite,
    selectView,
    removeGap,
    updateGap,
  }
}

const useCardActions = (removeGap: RemoveGap, updateGap: UpdateGap, announce: Announce) => {
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [cardErrors, setCardErrors] = useState<Record<string, string>>({})

  const setCardError = useCallback((gapId: string, message: string) => {
    setCardErrors((current) => ({ ...current, [gapId]: message }))
  }, [])

  // Dismiss and reopen are the same move: POST, then the card leaves this view.
  const moveCard = useCallback(
    (action: "dismiss" | "reopen", doneLabel: string, failure: string) =>
      async (gap: GapRecord) => {
        setPendingId(gap.id)
        setCardError(gap.id, "")
        try {
          const response = await staffWrite(`/api/knowledge-gaps/${gap.id}/${action}`, "POST", {})
          if (!response.ok && response.status !== CONFLICT) {
            setCardError(gap.id, failure)
            return
          }
          removeGap(gap.id)
          announce(`${doneLabel}: ${gap.question}`)
        } catch {
          setCardError(gap.id, failure)
        } finally {
          setPendingId(null)
        }
      },
    [announce, removeGap, setCardError],
  )

  const dismiss = useCallback(
    (gap: GapRecord) => moveCard("dismiss", "Dismissed", DISMISS_ERROR)(gap),
    [moveCard],
  )
  const reopen = useCallback(
    (gap: GapRecord) => moveCard("reopen", "Reopened", REOPEN_ERROR)(gap),
    [moveCard],
  )

  const saveNote = useCallback(
    async (gap: GapRecord, note: string) => {
      try {
        const response = await staffWrite(`/api/knowledge-gaps/${gap.id}`, "PATCH", {
          note: note || null,
        })
        if (!response.ok) return false
        updateGap(gap.id, { note: note || null })
        return true
      } catch {
        return false
      }
    },
    [updateGap],
  )

  return { pendingId, cardErrors, dismiss, reopen, saveNote }
}

const useAnswerFlow = (removeGap: RemoveGap, announce: Announce) => {
  const [answering, setAnswering] = useState<GapRecord | null>(null)
  const [repliesFor, setRepliesFor] = useState<ForGap<string[]> | null>(null)
  const [similarFor, setSimilarFor] = useState<ForGap<SimilarEntries> | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [saveError, setSaveError] = useState("")

  // Specialist wording and close entries are conveniences; the form works without them.
  const fetchExtras = useCallback(async (gap: GapRecord) => {
    const [replies, similar] = await Promise.allSettled([
      staffRead(`/api/knowledge-gaps/${gap.id}/replies`),
      staffRead(`/api/knowledge-gaps/${gap.id}/similar`),
    ])
    if (replies.status === "fulfilled" && replies.value.ok) {
      const body = (await replies.value.json()) as { items: string[] }
      setRepliesFor({ gapId: gap.id, value: body.items })
    }
    if (similar.status === "fulfilled" && similar.value.ok) {
      setSimilarFor({ gapId: gap.id, value: (await similar.value.json()) as SimilarEntries })
    }
  }, [])

  const openAnswer = useCallback(
    async (gap: GapRecord) => {
      setAnswering(gap)
      setSaveError("")
      await fetchExtras(gap)
    },
    [fetchExtras],
  )

  const closeAnswer = useCallback(() => setAnswering(null), [])

  const submitAnswer = useCallback(
    async (payload: AnswerPayload) => {
      if (!answering) return
      setSubmitting(true)
      setSaveError("")
      try {
        const response = await staffWrite(
          `/api/knowledge-gaps/${answering.id}/answer`,
          "POST",
          payload,
        )
        if (!response.ok) {
          setSaveError(await answerError(response))
          return
        }
        removeGap(answering.id)
        announce(`Saved an answer for: ${answering.question}`)
        setAnswering(null)
      } catch {
        setSaveError(ANSWER_ERROR)
      } finally {
        setSubmitting(false)
      }
    },
    [announce, answering, removeGap],
  )

  // Keyed by gap so a late response can never appear under another question.
  const replies = repliesFor && repliesFor.gapId === answering?.id ? repliesFor.value : []
  const similar = similarFor && similarFor.gapId === answering?.id ? similarFor.value : null

  return {
    answering,
    replies,
    similar,
    submitting,
    saveError,
    openAnswer,
    closeAnswer,
    submitAnswer,
  }
}

export const useSuggestedFaqsState = () => {
  const queueState = useGapQueue()
  const [announcement, setAnnouncement] = useState("")
  const actions = useCardActions(queueState.removeGap, queueState.updateGap, setAnnouncement)
  const answerFlow = useAnswerFlow(queueState.removeGap, setAnnouncement)
  const target = useSearchTarget()
  useOpenSearchTarget(target.gap, queueState.queue?.items ?? null, answerFlow.openAnswer)
  return { ...queueState, ...actions, ...answerFlow, announcement }
}
