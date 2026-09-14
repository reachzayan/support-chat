import { cn } from "cn"
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react"
import type { AnchorHTMLAttributes, ComponentProps } from "react"

const Pagination = ({ className, ...props }: ComponentProps<"nav">) => (
  <nav
    aria-label="Pagination"
    className={cn("mx-auto flex w-full justify-center", className)}
    {...props}
  />
)

const PaginationContent = ({ className, ...props }: ComponentProps<"ul">) => (
  <ul className={cn("flex flex-row items-center gap-1", className)} {...props} />
)

const PaginationItem = ({ className, ...props }: ComponentProps<"li">) => (
  <li className={cn("", className)} {...props} />
)

type PaginationLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { isActive?: boolean }

const PaginationLink = ({ className, isActive, children, ...props }: PaginationLinkProps) => (
  <a
    aria-current={isActive ? "page" : undefined}
    className={cn(
      "border-line text-ink hover:bg-ice focus-visible:ring-steel inline-flex size-8 items-center justify-center rounded-[8px] border text-xs font-bold no-underline outline-none focus-visible:ring-2",
      isActive ? "bg-primary text-primary-foreground hover:bg-primary" : "bg-paper",
      className,
    )}
    {...props}
  >
    {children ?? <span className="sr-only">Page</span>}
  </a>
)

const PaginationPrevious = ({
  className,
  children = "Previous",
  ...props
}: PaginationLinkProps) => (
  <PaginationLink
    aria-label="Go to previous page"
    className={cn("w-auto gap-1 px-2.5", className)}
    {...props}
  >
    <ChevronLeft aria-hidden="true" className="size-3.5" />
    <span>{children}</span>
  </PaginationLink>
)

const PaginationNext = ({ className, children = "Next", ...props }: PaginationLinkProps) => (
  <PaginationLink
    aria-label="Go to next page"
    className={cn("w-auto gap-1 px-2.5", className)}
    {...props}
  >
    <span>{children}</span>
    <ChevronRight aria-hidden="true" className="size-3.5" />
  </PaginationLink>
)

const PaginationEllipsis = ({ className, ...props }: ComponentProps<"span">) => (
  <span
    aria-hidden="true"
    className={cn("flex size-8 items-center justify-center", className)}
    {...props}
  >
    <MoreHorizontal className="size-4" />
  </span>
)

export {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
}
