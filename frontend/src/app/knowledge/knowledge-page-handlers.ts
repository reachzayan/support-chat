"use client"

import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react"

import {
  staffRead,
  staffWrite,
  type KbPageDetail,
  type KbChunkRecord,
  type KbPageRecord,
  type KbSourceRecord,
} from "@/components/admin/staff-api"
import { toast } from "@/components/ui/toast"

import {
  clearChunkEditLock,
  readChunkEditLock,
  writeChunkEditLock,
  type ChunkEditLock,
} from "./chunk-edit-lock"

const mergeChunk = (current: KbPageDetail | null, saved: KbChunkRecord) => {
  if (current === null) {
    return current
  }
  return {
    ...current,
    chunks: current.chunks.map((item) => (item.id === saved.id ? saved : item)),
  }
}

const chunkMatchesLock = (detail: KbPageDetail, lock: ChunkEditLock) => {
  const chunk = detail.chunks.find((item) => item.id === lock.chunkId)
  return chunk?.last_body_edit_id === lock.editId && chunk.body === lock.body
}

// oxlint-disable-next-line eslint/max-lines-per-function -- Page and chunk mutations share one local state boundary so rollback remains consistent.
export const useKnowledgePageHandlers = (
  setPages: Dispatch<SetStateAction<KbPageRecord[]>>,
  setPageDetail: Dispatch<SetStateAction<KbPageDetail | null>>,
  setSources: Dispatch<SetStateAction<KbSourceRecord[]>>,
) => {
  const [chunkErrors, setChunkErrors] = useState<Record<string, string>>({})
  const [chunkPendingIds, setChunkPendingIds] = useState<string[]>([])
  const [chunkNotice, setChunkNotice] = useState("")
  const pendingRef = useRef(new Set<string>())
  const inFlightEdits = useRef(new Set<string>())
  const resumeStarted = useRef(false)
  const handleSelectPage = useCallback(
    async (page: KbPageRecord) => {
      const response = await staffRead(`/api/kb-pages/${page.id}`)
      if (!response.ok) {
        return
      }
      setPageDetail((await response.json()) as KbPageDetail)
    },
    [setPageDetail],
  )

  const handleTogglePage = useCallback(
    async (page: KbPageRecord) => {
      const response = await staffWrite(`/api/kb-pages/${page.id}`, "PATCH", {
        enabled: !page.enabled,
      })
      if (response.ok) {
        const next = (await response.json()) as KbPageRecord
        setPages((current) => current.map((row) => (row.id === next.id ? next : row)))
        setPageDetail((current) =>
          current !== null && current.id === next.id
            ? { ...current, enabled: next.enabled }
            : current,
        )
      }
    },
    [setPageDetail, setPages],
  )

  const handleRetryPage = useCallback(
    async (page: KbPageRecord) => {
      const response = await staffWrite(`/api/kb-pages/${page.id}/retry`, "POST", {})
      if (!response.ok) {
        return
      }
      const source = (await response.json()) as KbSourceRecord
      setSources((current) => current.map((row) => (row.id === source.id ? source : row)))
    },
    [setSources],
  )

  const finishPending = (chunkId: string) => {
    pendingRef.current.delete(chunkId)
    setChunkPendingIds([...pendingRef.current])
  }

  const persistChunkBody = useCallback(
    async (pageId: string, chunkId: string, body: string, editId: string) => {
      writeChunkEditLock({ chunkId, pageId, editId, body })
      const response = await staffWrite(
        `/api/kb-chunks/${chunkId}`,
        "PATCH",
        { body, edit_id: editId },
        { keepalive: true },
      )
      if (response.status === 409) {
        const currentPage = await staffRead(`/api/kb-pages/${pageId}`)
        if (currentPage.ok) {
          setPageDetail((await currentPage.json()) as KbPageDetail)
        }
        clearChunkEditLock()
        return "conflict" as const
      }
      if (!response.ok) {
        clearChunkEditLock()
        throw new Error("Answer could not be saved")
      }
      const saved = (await response.json()) as KbChunkRecord
      setPageDetail((current) => mergeChunk(current, saved))
      clearChunkEditLock()
      return "saved" as const
    },
    [setPageDetail],
  )

  const saveChunkBody = useCallback(
    async (pageId: string, chunkId: string, body: string, editId: string) => {
      if (inFlightEdits.current.has(editId)) {
        return false
      }
      inFlightEdits.current.add(editId)
      pendingRef.current.add(chunkId)
      setChunkPendingIds([...pendingRef.current])
      const toastId = toast.add({ title: "Saving answer", type: "loading" })
      try {
        const outcome = await persistChunkBody(pageId, chunkId, body, editId)
        if (outcome === "conflict") {
          toast.update(toastId, {
            title: "This page changed during save",
            type: "warning",
            priority: "high",
          })
          return true
        }
        toast.update(toastId, { title: "Answer saved", type: "success" })
        return true
      } catch {
        toast.update(toastId, {
          title: "Answer could not be saved",
          type: "error",
          priority: "high",
        })
        return false
      } finally {
        inFlightEdits.current.delete(editId)
        finishPending(chunkId)
      }
    },
    [persistChunkBody],
  )

  useEffect(() => {
    if (resumeStarted.current) {
      return
    }
    const lock = readChunkEditLock()
    if (lock === null) {
      return
    }
    resumeStarted.current = true
    const resume = async () => {
      pendingRef.current.add(lock.chunkId)
      setChunkPendingIds([...pendingRef.current])
      let replay = true
      try {
        const currentPage = await staffRead(`/api/kb-pages/${lock.pageId}`)
        if (currentPage.ok) {
          const detail = (await currentPage.json()) as KbPageDetail
          if (chunkMatchesLock(detail, lock)) {
            setPageDetail(detail)
            clearChunkEditLock()
            toast.add({ title: "Answer already saved", type: "info" })
            replay = false
          }
        }
      } catch {
        replay = true
      }
      if (!replay) {
        pendingRef.current.delete(lock.chunkId)
        setChunkPendingIds([...pendingRef.current])
        return
      }
      await saveChunkBody(lock.pageId, lock.chunkId, lock.body, lock.editId)
    }
    void resume()
  }, [saveChunkBody, setPageDetail])

  const handleSaveChunk = useCallback(
    async (pageId: string, chunk: KbChunkRecord, body: string) => {
      if (pendingRef.current.size > 0) {
        return false
      }
      pendingRef.current.add(chunk.id)
      setChunkPendingIds([...pendingRef.current])
      return saveChunkBody(pageId, chunk.id, body, crypto.randomUUID())
    },
    [saveChunkBody],
  )

  const handleToggleChunk = useCallback(
    async (pageId: string, chunk: KbChunkRecord) => {
      if (pendingRef.current.has(chunk.id)) {
        return
      }
      const previous = chunk
      const enabled = !previous.enabled
      pendingRef.current.add(chunk.id)
      setChunkPendingIds([...pendingRef.current])
      setChunkErrors((current) => ({ ...current, [chunk.id]: "" }))
      setChunkNotice("")
      setPageDetail((current) =>
        current === null
          ? current
          : {
              ...current,
              chunks: current.chunks.map((item) =>
                item.id === chunk.id ? { ...item, enabled } : item,
              ),
            },
      )
      try {
        const response = await staffWrite(`/api/kb-chunks/${chunk.id}`, "PATCH", { enabled })
        if (response.status === 409) {
          const currentPage = await staffRead(`/api/kb-pages/${pageId}`)
          if (currentPage.ok) {
            setPageDetail((await currentPage.json()) as KbPageDetail)
          }
          setChunkNotice("This page changed during sync. Review the latest retrieved answers.")
          return
        }
        if (!response.ok) {
          throw new Error("This retrieved answer could not be updated. Try again.")
        }
        const saved = (await response.json()) as KbChunkRecord
        setPageDetail((current) => mergeChunk(current, saved))
      } catch (error) {
        setPageDetail((current) =>
          current === null
            ? current
            : {
                ...current,
                chunks: current.chunks.map((item) => (item.id === previous.id ? previous : item)),
              },
        )
        setChunkErrors((current) => ({
          ...current,
          [chunk.id]:
            error instanceof Error ? error.message : "This retrieved answer could not be updated.",
        }))
      } finally {
        finishPending(chunk.id)
      }
    },
    [setPageDetail],
  )

  return {
    handleSelectPage,
    handleTogglePage,
    handleRetryPage,
    handleToggleChunk,
    handleSaveChunk,
    chunkErrors,
    chunkPendingIds,
    chunkNotice,
  }
}
