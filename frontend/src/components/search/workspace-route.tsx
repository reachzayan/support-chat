"use client"
import { usePathname, useSearchParams } from "next/navigation"
/* oxlint-disable react-perf/jsx-no-jsx-as-prop -- Suspense fallback is static route loading feedback. */
import { createContext, useContext, useEffect, useRef, Suspense, type ReactNode } from "react"

import { toast } from "@/components/ui/toast"

export const SelectionContext = createContext<Readonly<Record<string, string>>>({})
export const useSearchTarget = () => useContext(SelectionContext)
const SelectedRoute = ({ children }: { children: ReactNode }) => {
  const params = useSearchParams()
  const pathname = usePathname()
  const selection = Object.fromEntries(params.entries())
  const key = [
    pathname,
    ...["site", "source", "page", "response", "gap", "log", "block", "scope", "view"].map(
      (name) => params.get(name) ?? "",
    ),
    pathname === "/admin/inbox" ? "" : (params.get("conversation") ?? ""),
  ].join(":")
  return (
    <SelectionContext.Provider key={key} value={selection}>
      {children}
    </SelectionContext.Provider>
  )
}
export const WorkspaceRoute = ({ children }: { children: ReactNode }) => (
  <Suspense fallback={<p className="text-mute p-6 text-sm">Opening workspace…</p>}>
    <SelectedRoute>{children}</SelectedRoute>
  </Suspense>
)

// URL destinations are read at the route boundary; each selected record opens once after loading.
export const useOpenSearchTarget = <T extends { id: string }>(
  id: string | undefined,
  records: T[] | null,
  open: (record: T) => unknown,
) => {
  const applied = useRef<string | null>(null)
  useEffect(() => {
    if (!id || records === null || applied.current === id) return
    const record = records.find((row) => row.id === id)
    applied.current = id
    if (record) {
      // oxlint-disable-next-line react/set-state-in-effect -- Apply an explicit URL selection after its records finish loading.
      void open(record)
    } else {
      toast.add({
        title: "This search result is no longer available",
        description: "It may have been removed. Search again for the latest records.",
        type: "warning",
      })
    }
  }, [id, records, open])
}
