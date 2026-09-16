import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: "Canned responses",
}

export default function AdminCannedResponsesLayout({ children }: { children: ReactNode }) {
  return children
}
