export const CHUNK_EDIT_LOCK_KEY = "supportchat:kb-chunk-edit"

export type ChunkEditLock = {
  chunkId: string
  pageId: string
  editId: string
  body: string
}

const storage = () => (typeof localStorage === "undefined" ? null : localStorage)

export const readChunkEditLock = (): ChunkEditLock | null => {
  const raw = storage()?.getItem(CHUNK_EDIT_LOCK_KEY) ?? null
  if (raw === null) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as Partial<ChunkEditLock>
    if (
      typeof parsed.chunkId !== "string" ||
      typeof parsed.pageId !== "string" ||
      typeof parsed.editId !== "string" ||
      typeof parsed.body !== "string"
    ) {
      return null
    }
    return {
      chunkId: parsed.chunkId,
      pageId: parsed.pageId,
      editId: parsed.editId,
      body: parsed.body,
    }
  } catch {
    return null
  }
}

export const writeChunkEditLock = (lock: ChunkEditLock) => {
  storage()?.setItem(CHUNK_EDIT_LOCK_KEY, JSON.stringify(lock))
}

export const clearChunkEditLock = () => {
  storage()?.removeItem(CHUNK_EDIT_LOCK_KEY)
}
