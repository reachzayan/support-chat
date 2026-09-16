import type { Metadata } from "next"
import type { ReactNode } from "react"

export const metadata: Metadata = {
  title: {
    absolute: "SupportChat",
  },
}

export default function WidgetLayout({ children }: { children: ReactNode }) {
  return children
}
