import type { ReactNode } from "react"

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
    <header className="border-line bg-paper flex min-h-[82px] flex-wrap items-center justify-between gap-4 border-b px-5 py-4 lg:px-8">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
            {eyebrow}
          </p>
        ) : null}
        <div className="flex items-center gap-2">
          <h1 className={`text-navy heading text-[1.65rem] ${eyebrow ? "mt-1" : ""}`}>{title}</h1>
          {titleAction}
        </div>
        {description ? <p className="text-mute mt-1 max-w-2xl text-xs">{description}</p> : null}
      </div>
      {action ? <div className="max-w-full shrink-0">{action}</div> : null}
    </header>
  )
}
