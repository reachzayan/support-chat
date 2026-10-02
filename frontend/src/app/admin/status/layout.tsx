import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: "Status",
}

export default function AdminStatusLayout({ children }: { children: ReactNode }) {
  return children
}
