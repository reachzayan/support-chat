import { cn } from "cn"

const Badge = ({ className, ...props }: React.ComponentProps<"span">) => {
  return (
    <span
      data-slot="badge"
      className={cn(
        "inline-flex items-center rounded-[8px] px-2 py-0.5 text-[10px] font-semibold tracking-[0.06em] uppercase",
        className,
      )}
      {...props}
    />
  )
}

export { Badge }
