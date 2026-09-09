import { cn } from "cn"

const Textarea = ({ className, ...props }: React.ComponentProps<"textarea">) => {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "border-line bg-ice text-ink focus-visible:ring-steel min-h-20 w-full rounded-[8px] border px-3 py-2.5 text-sm outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    />
  )
}

export { Textarea }
