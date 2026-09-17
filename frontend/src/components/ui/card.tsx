import { cn } from "cn"

const Card = ({ className, ...props }: React.ComponentProps<"div">) => {
  return (
    <div
      data-slot="card"
      className={cn("border-line bg-paper flex flex-col rounded-[8px] border", className)}
      {...props}
    />
  )
}

const CardHeader = ({ className, ...props }: React.ComponentProps<"div">) => {
  return (
    <div
      data-slot="card-header"
      className={cn("flex flex-col gap-1.5 border-b border-line px-4 py-3", className)}
      {...props}
    />
  )
}

const CardTitle = ({ className, children, ...props }: React.ComponentProps<"h3">) => {
  return (
    <h3 data-slot="card-title" className={cn("text-navy heading text-sm", className)} {...props}>
      {children}
    </h3>
  )
}

const CardContent = ({ className, ...props }: React.ComponentProps<"div">) => {
  return <div data-slot="card-content" className={cn("px-4 py-3", className)} {...props} />
}

export { Card, CardHeader, CardTitle, CardContent }
