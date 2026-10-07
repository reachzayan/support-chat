import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-transparent bg-clip-padding text-sm font-medium leading-none whitespace-nowrap transition-[transform,background-color,border-color,color,box-shadow,opacity] duration-150 ease-out outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:scale-[0.98] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground hover:bg-ember-mid hover:text-primary-foreground",
        outline:
          "border-line bg-paper text-navy hover:bg-ice-2 hover:text-navy aria-expanded:bg-ice-2 aria-expanded:text-navy dark:border-input dark:bg-paper dark:hover:bg-ice-2",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_5%)] aria-expanded:bg-secondary aria-expanded:text-secondary-foreground",
        ghost:
          "hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:hover:bg-muted/50",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20 focus-visible:border-destructive/40 focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:hover:bg-destructive/30 dark:focus-visible:ring-destructive/40",
        link: "text-primary",
      },
      size: {
        default: "h-8 px-3 has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5",
        xs: "h-6 gap-1 px-2 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 px-2.5 text-[0.8rem] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 px-3.5 has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        icon: "size-8",
        "icon-xs": "size-6 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-7 [&_svg:not([class*='size-'])]:size-3.5",
        "icon-lg": "size-9",
      },
    },
    compoundVariants: [
      {
        size: ["icon", "icon-xs", "icon-sm", "icon-lg"],
        variant: ["ghost", "link"],
        className: "hover:bg-transparent! aria-expanded:bg-transparent! dark:hover:bg-transparent!",
      },
      {
        size: ["icon", "icon-xs", "icon-sm", "icon-lg"],
        variant: "outline",
        className: "hover:bg-paper! aria-expanded:bg-paper! dark:hover:bg-paper!",
      },
      {
        size: ["icon", "icon-xs", "icon-sm", "icon-lg"],
        variant: "default",
        className: "hover:bg-primary!",
      },
      {
        size: ["icon", "icon-xs", "icon-sm", "icon-lg"],
        variant: "secondary",
        className: "hover:bg-secondary!",
      },
      {
        size: ["icon", "icon-xs", "icon-sm", "icon-lg"],
        variant: "destructive",
        className: "hover:bg-destructive/10! dark:hover:bg-destructive/20!",
      },
    ],
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
