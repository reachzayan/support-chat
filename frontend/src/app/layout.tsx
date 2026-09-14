import type { Metadata } from "next"

import "./globals.css"

export const metadata: Metadata = {
  title: "SupportChat",
  description: "Specialist chat for screening operations",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex h-full min-h-dvh flex-col font-sans">{children}</body>
    </html>
  )
}
