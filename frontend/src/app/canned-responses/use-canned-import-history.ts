import { useCallback, useEffect, useRef, useState } from "react"

import { staffRead } from "@/components/admin/staff-api"

export type ImportBatch = {
  id: number
  filename: string
  uploaded_at: string
  uploaded_by_name: string | null
  created: number
  updated: number
  skipped: number
}
export type ImportEntry = {
  row_number: number
  reply_id: string | null
  action: string
  snapshot: {
    shortcut: string
    body: string
    aliases?: string[]
    site_id: string | null
    reason: string | null
    livechat_id?: number | null
    bot_eligible?: boolean
    disable_reason?: string | null
  }
}
export type ImportDetail = { batch: ImportBatch; rows: ImportEntry[]; has_more: boolean }

const read = async <T>(path: string): Promise<T> => {
  const response = await staffRead(path)
  if (!response.ok) throw new Error("Could not load upload history. Try again.")
  return response.json() as Promise<T>
}

const saveOriginal = async (batch: ImportBatch) => {
  const response = await staffRead(`/api/canned-replies/imports/${batch.id}/file`)
  if (!response.ok) throw new Error("Could not download the file. Try again.")
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement("a")
  link.href = url
  link.download = batch.filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

// oxlint-disable-next-line eslint/max-lines-per-function -- One mounted history dialog owns its paginated requests and file download state.
export const useCannedImportHistory = () => {
  const [batches, setBatches] = useState<ImportBatch[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [detail, setDetail] = useState<ImportDetail | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const request = useRef(0)
  const load = useCallback(async (offset = 0) => {
    setBusy(true)
    setError("")
    try {
      const result = await read<{ items: ImportBatch[]; has_more: boolean }>(
        `/api/canned-replies/imports?offset=${offset}&limit=20`,
      )
      setBatches((current) => (offset === 0 ? result.items : [...current, ...result.items]))
      setHasMore(result.has_more)
    } catch {
      setError("Could not load upload history. Try again.")
    } finally {
      setBusy(false)
    }
  }, [])
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Fetch history when the dialog mounts.
    void load()
  }, [load])
  const view = useCallback(async (id: number, offset = 0) => {
    const next = ++request.current
    setSelected(id)
    setBusy(true)
    setError("")
    if (offset === 0) setDetail(null)
    try {
      const result = await read<ImportDetail>(
        `/api/canned-replies/imports/${id}?offset=${offset}&limit=100`,
      )
      if (next === request.current)
        setDetail((current) =>
          offset === 0 || !current
            ? result
            : { ...result, rows: [...current.rows, ...result.rows] },
        )
    } catch {
      if (next === request.current) setError("Could not load this upload. Try again.")
    } finally {
      if (next === request.current) setBusy(false)
    }
  }, [])
  const back = useCallback(() => {
    ++request.current
    setSelected(null)
    setDetail(null)
    setBusy(false)
    setError("")
  }, [])
  const download = useCallback(async (batch: ImportBatch) => {
    setBusy(true)
    setError("")
    try {
      await saveOriginal(batch)
    } catch {
      setError("Could not download the file. Try again.")
    } finally {
      setBusy(false)
    }
  }, [])
  return { batches, hasMore, selected, detail, busy, error, load, view, back, download }
}
