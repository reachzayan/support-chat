/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Controlled input handlers use current field values. */

import { Plus } from "lucide-react"
import { useCallback, useState, type ChangeEvent, type KeyboardEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogResizeSection,
  DialogTitle,
} from "@/components/ui/dialog"
import { FieldError } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup } from "@/components/ui/toggle-group"

const KNOWLEDGE_TYPE_OPTIONS = [
  { value: "website", label: "Website" },
  { value: "text", label: "Plain text" },
]

export const AddKnowledgeDialog = ({
  open,
  onOpenChange,
  siteName,
  urls,
  onUrls,
  onAdd,
  onAddText,
  busy,
  error,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  siteName: string
  urls: string
  onUrls: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onAdd: () => void
  onAddText: (title: string, body: string) => Promise<boolean>
  busy: boolean
  error: string | null
}) => {
  const form = useAddKnowledgeForm({ onOpenChange, onAddText })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl gap-0 p-0">
        <AddKnowledgeHeader siteName={siteName} />
        <AddKnowledgeFormBody
          kind={form.kind}
          onKindChange={form.handleKindChange}
          urls={urls}
          onUrls={onUrls}
          title={form.title}
          body={form.body}
          onTitle={form.setTitle}
          onBody={form.setBody}
          onTextKeyDown={form.handleTextKeyDown}
          error={error}
        />
        <AddKnowledgeFooter
          kind={form.kind}
          busy={busy}
          onCancel={form.handleCancel}
          onWebsite={onAdd}
          onText={form.handleTextSubmit}
        />
      </DialogContent>
    </Dialog>
  )
}

const useAddKnowledgeForm = ({
  onOpenChange,
  onAddText,
}: {
  onOpenChange: (open: boolean) => void
  onAddText: (title: string, body: string) => Promise<boolean>
}) => {
  const [kind, setKind] = useState<"website" | "text">("website")
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const handleCancel = useCallback(() => onOpenChange(false), [onOpenChange])
  const handleKindChange = useCallback((value: string) => {
    if (value === "website" || value === "text") {
      setKind(value)
    }
  }, [])
  const handleTextSubmit = useCallback(async () => {
    if (await onAddText(title, body)) {
      setTitle("")
      setBody("")
      onOpenChange(false)
    }
  }, [body, onAddText, onOpenChange, title])
  const handleTextKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault()
        void handleTextSubmit()
      }
    },
    [handleTextSubmit],
  )
  return {
    kind,
    title,
    body,
    setTitle,
    setBody,
    handleCancel,
    handleKindChange,
    handleTextSubmit,
    handleTextKeyDown,
  }
}

const AddKnowledgeFormBody = ({
  kind,
  onKindChange,
  urls,
  onUrls,
  title,
  body,
  onTitle,
  onBody,
  onTextKeyDown,
  error,
}: {
  kind: "website" | "text"
  onKindChange: (value: string) => void
  urls: string
  onUrls: (event: ChangeEvent<HTMLTextAreaElement>) => void
  title: string
  body: string
  onTitle: (value: string) => void
  onBody: (value: string) => void
  onTextKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  error: string | null
}) => (
  <DialogResizeSection className="flex flex-col gap-3 px-6 py-6">
    <ToggleGroup
      appearance="segmented"
      aria-label="Knowledge type"
      value={kind}
      onValueChange={onKindChange}
      options={KNOWLEDGE_TYPE_OPTIONS}
    />
    {kind === "website" ? (
      <WebsiteFields urls={urls} onUrls={onUrls} error={error} />
    ) : (
      <TextFields
        title={title}
        body={body}
        onTitle={onTitle}
        onBody={onBody}
        onKeyDown={onTextKeyDown}
        error={error}
      />
    )}
    <FieldError id="knowledge-add-error">{error ?? undefined}</FieldError>
  </DialogResizeSection>
)

const AddKnowledgeHeader = ({ siteName }: { siteName: string }) => (
  <DialogHeader className="bg-ice/70 px-6 py-5">
    <div className="bg-ember/10 text-ember mb-2 flex size-10 items-center justify-center rounded-lg">
      <Plus aria-hidden="true" className="size-5" strokeWidth={2.2} />
    </div>
    <DialogTitle className="text-lg">Add knowledge</DialogTitle>
    <DialogDescription className="max-w-md leading-5">
      Connect public pages or add trusted text for {siteName}.
    </DialogDescription>
  </DialogHeader>
)

const AddKnowledgeFooter = ({
  kind,
  busy,
  onCancel,
  onWebsite,
  onText,
}: {
  kind: "website" | "text"
  busy: boolean
  onCancel: () => void
  onWebsite: () => void
  onText: () => void
}) => (
  <DialogFooter className="flex-row items-center justify-end gap-2 px-6 py-4">
    <Button type="button" variant="outline" size="lg" onClick={onCancel}>
      Cancel
    </Button>
    <Button
      type="button"
      variant="default"
      size="lg"
      onClick={kind === "website" ? onWebsite : onText}
      disabled={busy}
      className="font-bold"
    >
      {busy ? (
        <Spinner data-icon="inline-start" />
      ) : (
        <Plus data-icon="inline-start" aria-hidden="true" />
      )}
      {busy ? "Adding…" : kind === "website" ? "Add pages" : "Add text"}
    </Button>
  </DialogFooter>
)

const WebsiteFields = ({
  urls,
  onUrls,
  error,
}: {
  urls: string
  onUrls: (event: ChangeEvent<HTMLTextAreaElement>) => void
  error: string | null
}) => (
  <div className="flex flex-col gap-3">
    <div>
      <label className="text-ink block text-sm font-medium" htmlFor="knowledge-urls">
        Website URL
      </label>
      <p className="text-mute mt-1 text-xs">
        One HTTPS URL crawls the site. Additional lines index only those pages.
      </p>
    </div>
    <Textarea
      id="knowledge-urls"
      name="pageUrls"
      autoComplete="off"
      value={urls}
      onChange={onUrls}
      placeholder="https://example.com/services"
      className="border-line bg-ice text-ink focus-visible:ring-steel min-h-24 w-full resize-y rounded-lg border px-3 py-3 font-mono text-base leading-6 outline-none focus-visible:ring-2 sm:text-sm"
      rows={3}
      aria-invalid={error ? "true" : undefined}
      aria-describedby="knowledge-add-error"
    />
  </div>
)

const TextFields = ({
  title,
  body,
  onTitle,
  onBody,
  onKeyDown,
  error,
}: {
  title: string
  body: string
  onTitle: (value: string) => void
  onBody: (value: string) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  error: string | null
}) => (
  <div className="flex flex-col gap-4">
    <div>
      <label className="text-ink block text-sm font-medium" htmlFor="knowledge-title">
        Title
      </label>
      <input
        id="knowledge-title"
        value={title}
        onChange={(event) => onTitle(event.target.value)}
        maxLength={300}
        className="border-line bg-ice text-ink focus-visible:ring-steel mt-2 h-10 w-full rounded-lg border px-3 text-base outline-none focus-visible:ring-2 sm:text-sm"
        placeholder="Collections policy"
        aria-invalid={error ? "true" : undefined}
        aria-describedby="knowledge-add-error"
      />
    </div>
    <div>
      <label className="text-ink block text-sm font-medium" htmlFor="knowledge-content">
        Content
      </label>
      <p className="text-mute mt-1 text-xs">
        Add verified information only. Do not include sensitive personal data.
      </p>
      <Textarea
        id="knowledge-content"
        value={body}
        onChange={(event) => onBody(event.target.value)}
        onKeyDown={onKeyDown}
        maxLength={40_000}
        rows={9}
        className="border-line bg-ice text-ink focus-visible:ring-steel mt-2 min-h-48 w-full resize-y rounded-lg border px-3 py-3 text-base leading-6 outline-none focus-visible:ring-2 sm:text-sm"
        placeholder="Paste the trusted information the assistant may use…"
        aria-invalid={error ? "true" : undefined}
        aria-describedby="knowledge-add-error"
      />
    </div>
  </div>
)
