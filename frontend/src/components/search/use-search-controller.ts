"use client"
import { usePathname, useRouter } from "next/navigation"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
  type RefObject,
} from "react"

import { searchScreen, screenLabel, type SearchItem } from "./search-destinations"
import { useWorkspaceSearch } from "./use-workspace-search"

export const useSearchDismiss = (
  open: boolean,
  close: (next: boolean) => void,
  inputRef: RefObject<HTMLInputElement | null>,
) => {
  const containerRef = useRef<HTMLElement>(null)
  useEffect(() => {
    if (!open) return
    const dismiss = (event: Event) => {
      if (event.target instanceof Node && !containerRef.current?.contains(event.target)) {
        close(false)
      }
    }
    const escape = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        !event.isComposing &&
        event.keyCode !== 229 &&
        event.target instanceof Node &&
        containerRef.current?.contains(event.target)
      ) {
        event.preventDefault()
        close(false)
        inputRef.current?.focus()
      }
    }
    document.addEventListener("pointerdown", dismiss)
    document.addEventListener("focusin", dismiss)
    document.addEventListener("keydown", escape)
    return () => {
      document.removeEventListener("pointerdown", dismiss)
      document.removeEventListener("focusin", dismiss)
      document.removeEventListener("keydown", escape)
    }
  }, [open, close, inputRef])
  return containerRef
}

export const useSearchController = (isAdmin: boolean) => {
  const currentScreen = searchScreen(usePathname())
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [retry, setRetry] = useState(0)
  const [composing, setComposing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const search = useWorkspaceSearch(query, currentScreen, isAdmin, open && !composing, retry)
  const onOpenChange = useCallback((next: boolean) => {
    setOpen(next)
    if (next) setRetry((value) => value + 1)
    if (!next) {
      setQuery("")
      setComposing(false)
    }
  }, [])
  const navigate = useCallback(
    (item: SearchItem, event?: MouseEvent<HTMLElement>) => {
      if (event && (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)) return
      event?.preventDefault()
      onOpenChange(false)
      router.push(item.href)
    },
    [onOpenChange, router],
  )
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        onOpenChange(!open)
        if (!open) inputRef.current?.focus()
      }
    }
    document.addEventListener("keydown", shortcut)
    return () => document.removeEventListener("keydown", shortcut)
  }, [onOpenChange, open])
  const { current: currentItems, navigation: navigationItems, other: otherItems } = search.results
  const groups = useMemo(
    () => [
      { label: `This screen · ${screenLabel(currentScreen)}`, items: currentItems },
      { label: "Go to", items: navigationItems },
      { label: "Other matches", items: otherItems },
    ],
    [currentScreen, currentItems, navigationItems, otherItems],
  )
  const items = useMemo(() => groups.flatMap((group) => group.items), [groups])
  const clear = () => {
    setQuery("")
    inputRef.current?.focus()
  }
  const retrySearch = () => setRetry((n) => n + 1)
  return {
    ...search,
    open,
    onOpenChange,
    query,
    setQuery,
    composing,
    setComposing,
    inputRef,
    groups,
    items,
    currentScreen,
    navigate,
    clear,
    retrySearch,
  }
}
export type SearchController = ReturnType<typeof useSearchController>
