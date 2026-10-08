import { cn } from "cn"
import type { ReactNode } from "react"

export const RECORD_LABEL = "text-mute text-[11px] font-bold tracking-[0.12em] uppercase"

export type RecordField = {
  label: string
  value: ReactNode
  mono?: boolean
  /** Span both columns (long values such as URLs, badges, messages). */
  wide?: boolean
}

/**
 * Small-screen replacement for a wide data table: one stacked card per record,
 * key fields first, secondary fields labelled, actions as full-size tap targets.
 * Render it instead of the table (see `useIsMobile`) so only one structure is in the DOM.
 */
export const RecordCardList = ({
  label,
  className,
  children,
}: {
  label: string
  className?: string
  children: ReactNode
}) => (
  <ul aria-label={label} className={cn("divide-line m-0 list-none divide-y p-0", className)}>
    {children}
  </ul>
)

export const RecordCard = ({
  title,
  titleTitle,
  eyebrow,
  badge,
  fields,
  actions,
  footer,
}: {
  title: ReactNode
  titleTitle?: string
  eyebrow?: ReactNode
  badge?: ReactNode
  fields: RecordField[]
  actions?: ReactNode
  footer?: ReactNode
}) => (
  <li className="px-4 py-4">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        {eyebrow ? <p className="text-mute truncate text-xs">{eyebrow}</p> : null}
        <p className="text-navy heading text-base wrap-anywhere" title={titleTitle}>
          {title}
        </p>
      </div>
      {badge ? <div className="shrink-0">{badge}</div> : null}
    </div>
    {fields.length > 0 ? (
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        {fields.map((field) => (
          <div key={field.label} className={cn("min-w-0", field.wide && "col-span-2")}>
            <dt className={RECORD_LABEL}>{field.label}</dt>
            <dd
              className={cn(
                "text-ink mt-0.5 wrap-anywhere",
                field.mono && "font-mono text-xs leading-5",
              )}
            >
              {field.value}
            </dd>
          </div>
        ))}
      </dl>
    ) : null}
    {footer ? <div className="text-mute mt-3 text-xs">{footer}</div> : null}
    {actions ? (
      <div className="mt-4 flex flex-wrap gap-2 [&_[data-slot=button]]:min-h-11 [&_[data-slot=button]]:flex-1">
        {actions}
      </div>
    ) : null}
  </li>
)
