import type { ReactNode } from "react"

export const StaffHeader = ({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) => {
  return (
    <header className="border-line bg-paper flex min-h-[82px] items-center justify-between gap-4 border-b px-5 py-4 lg:px-8">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
            {eyebrow}
          </p>
        ) : null}
        <h1 className={`text-navy heading text-[1.65rem] ${eyebrow ? "mt-1" : ""}`}>{title}</h1>
        {description ? <p className="text-mute mt-1 max-w-2xl text-xs">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  )
}
