import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: "Logs",
}

export default function AdminLogsLayout({ children }: { children: ReactNode }) {
  return children
}
