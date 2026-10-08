import type { Metadata } from "next"
import Link from "next/link"

import { BrandMark } from "@/components/brand-mark"
import { buttonVariants } from "@/components/ui/button"

export const metadata: Metadata = {
  title: "Page not found",
}

export default function NotFound() {
  return (
    <main
      id="main-content"
      className="bg-ice flex min-h-dvh flex-1 flex-col items-center justify-center px-5 py-12 text-center"
    >
      <BrandMark size={48} className="size-12" />
      <p className="text-ember mt-6 font-mono text-sm font-semibold tracking-[0.2em]">404</p>
      <h1 className="text-navy heading mt-2 text-2xl sm:text-3xl">This page could not be found</h1>
      <p className="text-mute mt-3 max-w-md text-sm leading-6">
        The address may be mistyped or the page may have moved. Staff consoles live under the admin
        workspace.
      </p>
      <div className="mt-8 flex w-full max-w-sm flex-col gap-3 sm:w-auto sm:max-w-none sm:flex-row">
        <Link
          href="/admin/inbox"
          className={`${buttonVariants({ variant: "default", size: "lg" })} min-h-11 px-5 font-bold no-underline`}
        >
          Go to the inbox
        </Link>
        <Link
          href="/login"
          className={`${buttonVariants({ variant: "outline", size: "lg" })} min-h-11 px-5 font-bold no-underline`}
        >
          Sign in
        </Link>
      </div>
    </main>
  )
}
