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
    <button type="button" className="underline underline-offset-2" onClick={onRetry}>
      Retry
    </button>
  </p>
)
