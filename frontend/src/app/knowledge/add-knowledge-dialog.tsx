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
import { Textarea } from "@/components/ui/textarea"

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
  const [kind, setKind] = useState<"website" | "text">("website")
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const handleCancel = useCallback(() => onOpenChange(false), [onOpenChange])
  const showWebsite = useCallback(() => setKind("website"), [])
  const showText = useCallback(() => setKind("text"), [])
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
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl gap-0 p-0">
        <AddKnowledgeHeader siteName={siteName} />
        <DialogResizeSection className="flex flex-col gap-3 px-6 py-6">
          <KnowledgeTypePicker kind={kind} onWebsite={showWebsite} onText={showText} />
          {kind === "website" ? (
            <WebsiteFields urls={urls} onUrls={onUrls} error={error} />
          ) : (
            <TextFields
              title={title}
              body={body}
              onTitle={setTitle}
              onBody={setBody}
              onKeyDown={handleTextKeyDown}
              error={error}
            />
          )}
          <FieldError id="knowledge-add-error">{error ?? undefined}</FieldError>
        </DialogResizeSection>
        <AddKnowledgeFooter
          kind={kind}
          busy={busy}
          onCancel={handleCancel}
          onWebsite={onAdd}
          onText={handleTextSubmit}
        />
      </DialogContent>
    </Dialog>
  )
}

const AddKnowledgeHeader = ({ siteName }: { siteName: string }) => (
  <DialogHeader className="bg-ice/70 px-6 py-5">
    <div className="bg-ember/10 text-ember mb-2 flex size-10 items-center justify-center rounded-[10px]">
      <Plus aria-hidden="true" className="size-5" strokeWidth={2.2} />
    </div>
    <DialogTitle className="text-lg">Add knowledge</DialogTitle>
    <DialogDescription className="max-w-md leading-5">
      Connect public pages or add trusted text for {siteName}.
    </DialogDescription>
  </DialogHeader>
)

const KnowledgeTypePicker = ({
  kind,
  onWebsite,
  onText,
}: {
  kind: "website" | "text"
  onWebsite: () => void
  onText: () => void
}) => (
  <div className="bg-ice-2 flex w-fit gap-1 rounded-[9px] p-1" aria-label="Knowledge type">
    <button
      type="button"
      aria-pressed={kind === "website"}
      onClick={onWebsite}
      className={`rounded-[7px] px-3 py-2 text-xs font-bold ${kind === "website" ? "bg-paper text-navy shadow-sm" : "text-mute"}`}
    >
      Website
    </button>
    <button
      type="button"
      aria-pressed={kind === "text"}
      onClick={onText}
      className={`rounded-[7px] px-3 py-2 text-xs font-bold ${kind === "text" ? "bg-paper text-navy shadow-sm" : "text-mute"}`}
    >
      Plain text
    </button>
  </div>
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
  <DialogFooter className="flex-row justify-end gap-2 px-6 py-4">
    <Button type="button" variant="ghost" onClick={onCancel}>
      Cancel
    </Button>
    <Button
      type="button"
      onClick={kind === "website" ? onWebsite : onText}
      disabled={busy}
      className="bg-ember hover:bg-ember-mid focus-visible:ring-steel rounded-[9px] px-4 text-sm font-bold text-white focus-visible:ring-2 focus-visible:outline-none"
    >
      <Plus aria-hidden="true" />
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
      className="border-line bg-ice text-ink focus-visible:ring-steel min-h-24 w-full resize-y rounded-[9px] border px-3 py-3 font-mono text-base leading-6 outline-none focus-visible:ring-2 sm:text-sm"
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
        className="border-line bg-ice text-ink focus-visible:ring-steel mt-2 h-10 w-full rounded-[9px] border px-3 text-base outline-none focus-visible:ring-2 sm:text-sm"
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
        className="border-line bg-ice text-ink focus-visible:ring-steel mt-2 min-h-48 w-full resize-y rounded-[9px] border px-3 py-3 text-base leading-6 outline-none focus-visible:ring-2 sm:text-sm"
        placeholder="Paste the trusted information the assistant may use…"
        aria-invalid={error ? "true" : undefined}
        aria-describedby="knowledge-add-error"
      />
    </div>
  </div>
)
