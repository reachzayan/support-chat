import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: "Demo",
}

export default function DemoLayout({ children }: { children: ReactNode }) {
  return children
}
