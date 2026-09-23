import { Button } from "@/components/ui/button"

export const RetryError = ({
  text,
  onRetry,
  className = "mt-2",
}: {
  text: string
  onRetry: () => void
  className?: string
}) => (
  <p className={`text-ember text-xs ${className}`} role="alert">
    {text}{" "}
    <Button type="button" variant="link" size="sm" onClick={onRetry}>
      Retry
    </Button>
  </p>
)
