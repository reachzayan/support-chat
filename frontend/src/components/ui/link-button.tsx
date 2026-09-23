import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import type { ComponentProps } from "react"

import { Button } from "./button"

const linkUnderlineClass =
  "relative no-underline after:pointer-events-none after:absolute after:-bottom-px after:left-0 after:h-px after:w-full after:origin-left after:scale-x-0 after:bg-current after:transition-transform after:duration-200 after:ease-[cubic-bezier(0.23,1,0.32,1)] hover:after:scale-x-100 motion-reduce:after:transition-none motion-reduce:hover:after:scale-x-100"

const linkButtonVariants = cva(
  `${linkUnderlineClass} inline-flex cursor-pointer items-center gap-1.5 border-0 bg-transparent p-0 text-xs font-bold transition-colors duration-150 ease-out outline-none focus-visible:ring-2 focus-visible:ring-steel focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:after:scale-x-0`,
  {
    variants: {
      variant: {
        default: "text-steel hover:text-navy",
        ember: "text-ember hover:text-ember-mid",
        emphasis: "text-ember hover:text-navy",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

type LinkButtonProps = ComponentProps<"button"> & VariantProps<typeof linkButtonVariants>

const LinkButton = ({ className, variant, type = "button", ...props }: LinkButtonProps) => (
  <Button
    type={type}
    variant="link"
    className={cn(linkButtonVariants({ variant }), className)}
    {...props}
  />
)

export { LinkButton, linkButtonVariants, linkUnderlineClass }
