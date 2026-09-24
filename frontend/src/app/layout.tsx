import type { Metadata } from "next"
import localFont from "next/font/local"
import { cookies, headers } from "next/headers"

import { AppProviders } from "@/components/app-providers"

import "./globals.css"

const manrope = localFont({
  src: "./fonts/Manrope-variable.ttf",
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

const htmlClassName = (theme: Theme) =>
  theme === "dark"
    ? `${manrope.variable} h-full antialiased dark`
    : `${manrope.variable} h-full antialiased`

const staffChrome = async () => {
  const jar = await cookies()
  return {
    theme: readTheme(jar.get("supportchat_theme")?.value),
    sidebarOpen: jar.get("sidebar_state")?.value !== "false",
  }
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const isWidget = (await headers()).get("x-supportchat-surface") === "widget"
  const chrome = isWidget ? { theme: "light" as Theme, sidebarOpen: true } : await staffChrome()

  return (
    <html lang="en" className={htmlClassName(chrome.theme)} suppressHydrationWarning>
      <body
        className={`flex h-full min-h-dvh flex-col font-sans${isWidget ? " bg-transparent" : ""}`}
      >
        {isWidget ? (
          children
        ) : (
          <AppProviders initialTheme={chrome.theme} initialSidebarOpen={chrome.sidebarOpen}>
            {children}
          </AppProviders>
        )}
      </body>
    </html>
  )
}
