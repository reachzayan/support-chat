import { type FormEvent, type KeyboardEvent, type RefObject } from "react"
/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-new-array-as-prop, react-perf/jsx-no-jsx-as-prop -- Controlled form handlers and Base UI render props use current form values. */

import { type SiteRecord } from "@/components/admin/staff-api"
import {
  AlertDialog,
  AlertDialogClose,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { FieldError } from "@/components/ui/field"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"

import { scopeLabel, type CannedReplyRecord, type FormState } from "./canned-response-model"
import { CannedResponseSelect, scopeOptions } from "./canned-response-select"

const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter")
    event.currentTarget.form?.requestSubmit()
}

// oxlint-disable-next-line eslint/max-lines-per-function -- Form fields, scope picker, and submit validation stay together for one reviewable edit flow.
export const ResponseForm = ({
  form,
  sites,
  formError,
  submitting,
  onChange,
  onSubmit,
  onRequestClose,
  shortcutRef,
}: {
  form: FormState | null
  sites: SiteRecord[]
  formError: string
  submitting: boolean
  onChange: (next: FormState) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onRequestClose: () => void
  shortcutRef: RefObject<HTMLInputElement | null>
}) => {
  return (
    <Dialog
      open={form !== null}
      onOpenChange={(open) => {
        if (!open) onRequestClose()
      }}
    >
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>{form?.id ? "Edit canned response" : "Add canned response"}</DialogTitle>
          <DialogDescription>
            Plain-text wording is inserted into the composer for staff to review before sending.
          </DialogDescription>
        </DialogHeader>
        {form ? (
          <form onSubmit={onSubmit} className="flex min-h-0 flex-1 flex-col overflow-y-auto">
            <div className="flex flex-col gap-4 px-5 py-5">
              <label
                htmlFor="canned-response-scope"
                className="text-ink flex flex-col gap-1.5 text-sm font-medium"
              >
                Scope
                <CannedResponseSelect
                  id="canned-response-scope"
                  value={form.siteId ?? "general"}
                  onValueChange={(value) =>
                    onChange({ ...form, siteId: value === "general" ? null : value })
                  }
                  items={scopeOptions(sites)}
                />
              </label>
              <label className="text-ink flex flex-col gap-1.5 text-sm font-medium">
                Shortcut
                <span className="border-line bg-ice flex h-10 items-center rounded-[8px] border px-3">
                  <span className="text-mute font-mono">#</span>
                  <input
                    ref={shortcutRef}
                    value={form.shortcut}
                    maxLength={40}
                    onChange={(event) => onChange({ ...form, shortcut: event.target.value })}
                    aria-invalid={formError.includes("shortcut") || undefined}
                    className="text-ink min-w-0 flex-1 bg-transparent p-0 font-mono text-sm outline-none focus-visible:ring-0"
                  />
                </span>
                <span className="text-mute text-xs">{form.shortcut.length}/40 characters</span>
              </label>
              <label className="text-ink flex flex-col gap-1.5 text-sm font-medium">
                Message
                <Textarea
                  value={form.body}
                  maxLength={4000}
                  onKeyDown={keyDown}
                  onChange={(event) => onChange({ ...form, body: event.target.value })}
                  aria-invalid={formError.includes("Message") || undefined}
                />
                <span className="text-mute text-xs">
                  {form.body.length}/4,000 characters · Ctrl/⌘+Enter to save
                </span>
              </label>
              <label
                htmlFor="canned-response-enabled"
                className="border-line bg-ice text-ink flex items-center justify-between gap-3 rounded-[8px] border px-3 py-2.5 text-sm font-medium"
              >
                <span>
                  <span className="block">Enabled</span>
                  <span className="text-mute block text-xs font-normal">
                    Available in the inbox when this scope is active.
                  </span>
                </span>
                <Switch
                  id="canned-response-enabled"
                  checked={form.enabled}
                  onCheckedChange={(enabled) => onChange({ ...form, enabled })}
                  aria-label="Enabled"
                />
              </label>
              <FieldError>{formError || undefined}</FieldError>
            </div>
            <DialogFooter className="flex-row justify-end">
              <Button type="button" variant="outline" onClick={onRequestClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={submitting} className="bg-ember hover:bg-ember/90">
                {submitting ? "Saving…" : form.id ? "Save changes" : "Save response"}
              </Button>
            </DialogFooter>
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

export const DeleteDialog = ({
  target,
  sites,
  deleting,
  onCancel,
  onConfirm,
}: {
  target: CannedReplyRecord | null
  sites: SiteRecord[]
  deleting: boolean
  onCancel: () => void
  onConfirm: () => void
}) => (
  <AlertDialog
    open={target !== null}
    onOpenChange={(open) => {
      if (!open) onCancel()
    }}
  >
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>Remove canned response?</AlertDialogTitle>
        <AlertDialogDescription>
          {target
            ? `#${target.shortcut} in ${target.site_id === null ? "General" : scopeLabel(target.site_id, sites)} will be permanently deleted. Disabling keeps it available for later.`
            : ""}
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogClose render={<Button variant="outline">Cancel</Button>} />
        <Button variant="destructive" disabled={deleting} onClick={onConfirm}>
          {deleting ? "Removing…" : "Remove response"}
        </Button>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
)
