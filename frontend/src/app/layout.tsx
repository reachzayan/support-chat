import type { Metadata } from "next"
import { Manrope } from "next/font/google"
import { cookies } from "next/headers"

import { AppProviders } from "@/components/app-providers"

import "./globals.css"

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  display: "swap",
})

export const metadata: Metadata = {
  title: {
    default: "SupportChat",
    template: "%s | SupportChat",
  },
  description: "Specialist chat for screening operations",
}

type Theme = "light" | "dark"

const readTheme = (value: string | undefined): Theme => {
  if (value === "dark" || value === "light") {
    return value
  }
  return "light"
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const jar = await cookies()
  const initialTheme = readTheme(jar.get("supportchat_theme")?.value)
  const initialSidebarOpen = jar.get("sidebar_state")?.value !== "false"

  return (
    <html
      lang="en"
      className={`${manrope.variable} h-full antialiased${initialTheme === "dark" ? " dark" : ""}`}
      suppressHydrationWarning
    >
      <body className="flex h-full min-h-dvh flex-col font-sans">
        <AppProviders initialTheme={initialTheme} initialSidebarOpen={initialSidebarOpen}>
          {children}
        </AppProviders>
      </body>
    </html>
  )
}
