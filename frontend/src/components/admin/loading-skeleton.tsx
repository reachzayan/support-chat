import { Skeleton } from "@/components/ui/skeleton"

export const StaffPageSkeleton = () => (
  <div
    aria-label="Loading admin workspace"
    className="view-transition-enter flex min-h-0 flex-1 flex-col gap-6 p-5 lg:p-8"
  >
    <div className="flex items-center gap-3">
      <Skeleton className="size-9" />
      <Skeleton className="h-5 w-32" />
    </div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <Skeleton className="h-24" />
      <Skeleton className="h-24" />
      <Skeleton className="h-24 sm:col-span-2 xl:col-span-1" />
    </div>
    <div className="border-line bg-paper flex min-h-0 flex-1 flex-col gap-4 rounded-[8px] border p-5">
      <Skeleton className="h-5 w-44" />
      <Skeleton className="h-4 w-72 max-w-full" />
      <Skeleton className="h-44 w-full" />
    </div>
  </div>
)

export const DataTableSkeleton = () => (
  <section
    aria-label="Loading submissions"
    className="border-line bg-paper flex min-h-0 flex-1 flex-col gap-4 rounded-[8px] border p-5"
  >
    <div className="flex items-center justify-between gap-4">
      <Skeleton className="h-5 w-48" />
      <Skeleton className="h-8 w-24" />
    </div>
    <Skeleton className="h-4 w-72 max-w-full" />
    <div className="border-line overflow-hidden rounded-md border">
      {Array.from({ length: 6 }, (_, index) => (
        <div
          key={index}
          className="border-line flex items-center gap-4 border-b px-3 py-3 last:border-b-0"
        >
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  </section>
)

export const LogTableSkeleton = () => (
  <section
    aria-label="Loading logs"
    className="border-line bg-paper flex min-h-0 flex-1 flex-col gap-4 rounded-[8px] border p-5"
  >
    <div className="flex items-center justify-between gap-4">
      <Skeleton className="h-5 w-48" />
      <Skeleton className="h-8 w-32" />
    </div>
    <div className="border-line overflow-hidden rounded-md border">
      {Array.from({ length: 7 }, (_, index) => (
        <div
          key={index}
          className="border-line flex items-center gap-4 border-b px-3 py-3 last:border-b-0"
        >
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 flex-1" />
        </div>
      ))}
    </div>
  </section>
)
