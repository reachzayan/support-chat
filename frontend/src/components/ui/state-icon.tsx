import { cn } from "cn"

// Official Phosphor regular/fill artwork, vendored in public/icons/phosphor.svg.
export type StateIconName =
  | "arrow-clockwise"
  | "arrow-up"
  | "arrows-in-simple"
  | "arrows-out-simple"
  | "bell"
  | "book-open"
  | "chat-text"
  | "dots-three"
  | "eye"
  | "eye-slash"
  | "globe"
  | "hash"
  | "info"
  | "lightbulb"
  | "list"
  | "magnifying-glass"
  | "moon"
  | "pencil-simple"
  | "power"
  | "prohibit"
  | "pulse"
  | "scroll"
  | "sidebar-simple"
  | "sun"
  | "table"
  | "trash"
  | "tray"
  | "x-circle"
  | "x"

export const StateIcon = ({ name, className }: { name: StateIconName; className?: string }) => (
  <svg
    aria-hidden="true"
    focusable="false"
    viewBox="0 0 256 256"
    fill="currentColor"
    stroke="none"
    className={cn("state-icon size-4 shrink-0", className)}
  >
    <use className="state-icon-regular" href={`/icons/phosphor.svg#${name}-regular`} />
    <use className="state-icon-fill" href={`/icons/phosphor.svg#${name}-fill`} />
  </svg>
)
