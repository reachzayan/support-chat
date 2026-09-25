"use client"

import { Copy } from "lucide-react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { useCallback, type ComponentProps } from "react"

import { Button } from "@/components/ui/button"
import { useCopyFeedback } from "@/hooks/use-copy-feedback"
import { cn } from "@/lib/utils"

const LABEL_TRANSITION = { duration: 0.18, ease: [0.23, 1, 0.32, 1] as const }
const ZERO_TRANSITION = { duration: 0 }
const COPY_INITIAL = { opacity: 0, y: 5 }
const COPY_ANIMATE = { opacity: 1, y: 0 }
const COPY_EXIT = { opacity: 0, y: -5 }

type CopyButtonProps = Omit<ComponentProps<typeof Button>, "children" | "onClick"> & {
  value: string
  label?: string
}

export const CopyButton = ({
  value,
  label = "Copy snippet",
  className,
  size = "default",
  ...props
}: CopyButtonProps) => {
  const { copied, copy } = useCopyFeedback()
  const reducedMotion = useReducedMotion()
  const handleCopy = useCallback(() => {
    void copy(value)
  }, [copy, value])
  const initial = reducedMotion ? false : COPY_INITIAL
  const exit = reducedMotion ? undefined : COPY_EXIT
  const transition = reducedMotion ? ZERO_TRANSITION : LABEL_TRANSITION

  return (
    <Button
      {...props}
      type="button"
      variant="outline"
      size={size}
      onClick={handleCopy}
      aria-label={copied ? "Copied" : label}
      className={cn("min-w-[8.25rem]", className)}
    >
      <Copy data-icon="inline-start" aria-hidden="true" />
      <span className="relative inline-grid min-w-[5.75rem] place-items-center overflow-hidden leading-none">
        <AnimatePresence initial={false} mode="wait">
          <motion.span
            key={copied ? "copied" : "copy"}
            initial={initial}
            animate={COPY_ANIMATE}
            exit={exit}
            transition={transition}
            className="col-start-1 row-start-1 inline-block leading-none"
          >
            {copied ? "Copied" : label}
          </motion.span>
        </AnimatePresence>
      </span>
    </Button>
  )
}
