import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: "Blocked",
}

export default function AdminBlockedLayout({ children }: { children: ReactNode }) {
  return children
}
