import { cn } from "cn"

export const UnreadBadge = ({ count, className }: { count: number; className?: string }) =>
  count > 0 ? (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-[#C45516] px-1 text-[11px] leading-none font-semibold text-white tabular-nums",
        className,
      )}
    >
      {count > 99 ? "99+" : count}
    </span>
  ) : null
