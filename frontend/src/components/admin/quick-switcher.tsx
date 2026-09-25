"use client"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-new-object-as-prop, react-perf/jsx-no-jsx-as-prop -- Quick-switcher rows are a short, static, per-item handler list; the trigger's render prop mirrors the existing Popover/Button render-prop pattern used across this codebase. */

import { Search } from "lucide-react"
import { motion } from "motion/react"
import { useRouter } from "next/navigation"
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { matchesSearchQuery } from "@/lib/search"

export type QuickSwitcherLink = {
  href: string
  label: string
}

const MotionButton = motion.create(Button)

type QuickSwitcherProps = {
  links: QuickSwitcherLink[]
}

const useOpenShortcut = (onOpen: () => void) => {
  useEffect(() => {
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        onOpen()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [onOpen])
}

// oxlint-disable-next-line eslint/max-lines-per-function -- Keyboard navigation, filtering, and the trigger/popover markup are one reviewable interaction contract.
export const QuickSwitcher = ({ links }: QuickSwitcherProps) => {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const deferredQuery = useDeferredValue(query)

  const results = useMemo(() => {
    return links.filter((link) => matchesSearchQuery([link.label], deferredQuery))
  }, [deferredQuery, links])

  const closeAndReset = useCallback(() => {
    setOpen(false)
    setQuery("")
    setActiveIndex(0)
  }, [])

  const focusInput = useCallback(() => {
    requestAnimationFrame(() => inputRef.current?.focus())
  }, [])

  const handleOpen = useCallback(() => {
    setOpen(true)
    focusInput()
  }, [focusInput])

  useOpenShortcut(handleOpen)

  const go = useCallback(
    (href: string) => {
      router.push(href)
      closeAndReset()
    },
    [router, closeAndReset],
  )

  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (next) {
        handleOpen()
      } else {
        closeAndReset()
      }
    },
    [handleOpen, closeAndReset],
  )

  const handleQueryChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value)
    setActiveIndex(0)
  }, [])

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Escape") {
        event.preventDefault()
        closeAndReset()
        return
      }
      if (event.key === "ArrowDown") {
        event.preventDefault()
        setActiveIndex((current) => Math.min(current + 1, Math.max(results.length - 1, 0)))
        return
      }
      if (event.key === "ArrowUp") {
        event.preventDefault()
        setActiveIndex((current) => Math.max(current - 1, 0))
        return
      }
      if (event.key === "Enter" && results[activeIndex]) {
        event.preventDefault()
        go(results[activeIndex].href)
      }
    },
    [activeIndex, results, go, closeAndReset],
  )

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        onClick={handleOpen}
        render={
          <Button
            type="button"
            variant="ghost"
            aria-label="Search admin workspace"
            className="group flex h-9 w-full max-w-[15rem] items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3.5 text-left text-[13px] leading-none text-white/45 transition-colors duration-150 hover:border-white/15 hover:bg-white/[0.08] hover:text-white/75 sm:max-w-xs"
          />
        }
      >
        <Search aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={2} />
        <span className="flex-1 truncate">Find a page</span>
        <kbd className="hidden shrink-0 rounded-[5px] border border-white/10 bg-white/[0.05] px-1.5 py-0.5 font-mono text-[10px] text-white/35 sm:inline">
          ⌘K
        </kbd>
      </PopoverTrigger>
      <PopoverContent className="w-[min(20rem,calc(100vw-2rem))] p-2">
        <label htmlFor="quick-switcher-input" className="sr-only">
          Jump to
        </label>
        <Input
          ref={inputRef}
          id="quick-switcher-input"
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="Jump to…"
          value={query}
          onChange={handleQueryChange}
          onKeyDown={handleKeyDown}
          className="border-line bg-ice text-ink h-9 rounded-[8px] text-sm"
        />
        <div className="mt-2 flex flex-col gap-0.5">
          {results.length === 0 ? (
            <p className="text-mute px-2 py-3 text-center text-xs">
              No workspace pages match “{query.trim()}”.
            </p>
          ) : (
            results.map((link, index) => (
              <MotionButton
                key={link.href}
                type="button"
                variant="ghost"
                onClick={() => go(link.href)}
                onMouseEnter={() => setActiveIndex(index)}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.14, delay: index * 0.02 }}
                className={`rounded-[8px] px-2.5 py-2 text-left text-sm font-semibold transition-colors duration-100 ${
                  index === activeIndex ? "bg-ice-2 text-navy" : "text-ink hover:bg-ice-2"
                }`}
              >
                {link.label}
              </MotionButton>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
