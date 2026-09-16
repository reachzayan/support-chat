import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: "Inbox",
}

export default function AdminInboxLayout({ children }: { children: ReactNode }) {
  return children
}
