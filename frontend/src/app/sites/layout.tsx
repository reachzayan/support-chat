import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: "Sites",
}

export default function SitesLayout({ children }: { children: ReactNode }) {
  return children
}
