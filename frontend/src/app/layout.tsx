import type { Metadata } from "next"
import localFont from "next/font/local"

import "./globals.css"

const manrope = localFont({
  src: "./fonts/Manrope-variable.ttf",
  variable: "--font-manrope",
  display: "swap",
  weight: "300 800",
})

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
    <html lang="en" className={`${manrope.variable} h-full antialiased`}>
      <body className="flex h-full min-h-dvh flex-col font-sans">{children}</body>
    </html>
  )
}
