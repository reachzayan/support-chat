import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: "Knowledge base",
}

export default function KnowledgeLayout({ children }: { children: ReactNode }) {
  return children
}
