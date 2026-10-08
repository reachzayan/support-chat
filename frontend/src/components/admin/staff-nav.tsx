import type { ReactNode } from "react"

/** Shared padding for console bodies so headers and content line up on every screen size. */
export const STAFF_CONTENT_PADDING = "px-4 py-4 sm:px-5 sm:py-6 lg:px-8 lg:py-8"

export const StaffHeader = ({
  eyebrow,
  title,
  description,
  action,
  titleAction,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
  titleAction?: ReactNode
}) => {
  return (
    <header className="border-line bg-paper flex min-h-[72px] flex-wrap items-center justify-between gap-x-4 gap-y-3 border-b px-4 py-3 sm:min-h-[82px] sm:px-5 sm:py-4 lg:px-8">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
            {eyebrow}
          </p>
        ) : null}
        <div className="flex items-center gap-2">
          <h1 className={`text-navy heading text-xl sm:text-[1.65rem] ${eyebrow ? "mt-1" : ""}`}>
            {title}
          </h1>
          {titleAction}
        </div>
        {description ? (
          <p className="text-mute mt-1 max-w-2xl text-xs leading-5">{description}</p>
        ) : null}
      </div>
      {action ? (
        <div className="max-w-full shrink-0 max-md:w-full max-md:[&_[data-slot=button]]:min-h-11 max-md:[&_[data-slot=button]]:flex-1">
          {action}
        </div>
      ) : null}
    </header>
  )
}
