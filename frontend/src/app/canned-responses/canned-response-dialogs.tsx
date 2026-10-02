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
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"

import {
  followOptions,
  NO_PARENT,
  scopeLabel,
  type CannedReplyRecord,
  type FormState,
  BODY_MAX,
} from "./canned-response-model"
import { CannedResponseSelect, scopeOptions } from "./canned-response-select"

const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter")
    event.currentTarget.form?.requestSubmit()
}

// oxlint-disable-next-line eslint/max-lines-per-function, eslint/complexity -- Form fields, scope picker, and submit validation stay together for one reviewable edit flow.
export const ResponseForm = ({
  form,
  records,
  sites,
  formError,
  submitting,
  onChange,
  onSubmit,
  onRequestClose,
  shortcutRef,
}: {
  form: FormState | null
  records: CannedReplyRecord[]
  sites: SiteRecord[]
  formError: string
  submitting: boolean
  onChange: (next: FormState) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onRequestClose: () => void
  shortcutRef: RefObject<HTMLInputElement | null>
}) => {
  const blockedReason = records.find((row) => row.id === form?.id)?.bot_block_reason ?? null
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
          <form onSubmit={onSubmit} className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-none px-5 py-5">
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
                Additional shortcuts
                <input
                  value={form.aliasesText}
                  onChange={(event) => onChange({ ...form, aliasesText: event.target.value })}
                  placeholder="optional, comma-separated"
                  aria-label="Additional shortcuts"
                  className="border-line bg-ice text-ink focus-visible:ring-steel h-10 rounded-[8px] border px-3 font-mono text-sm outline-none focus-visible:ring-2"
                />
                <span className="text-mute text-xs">
                  Same as LiveChat extra tags. Type #any of them in the inbox to insert this reply.
                </span>
              </label>
              <label className="text-ink flex flex-col gap-1.5 text-sm font-medium">
                Message
                <Textarea
                  value={form.body}
                  maxLength={BODY_MAX}
                  onKeyDown={keyDown}
                  onChange={(event) => onChange({ ...form, body: event.target.value })}
                  aria-invalid={formError.includes("Message") || undefined}
                />
                <span className="text-mute text-xs">
                  {form.body.length}/{BODY_MAX.toLocaleString()} characters · Ctrl/⌘+Enter to save
                </span>
              </label>
              <div className="text-ink flex flex-col gap-1.5 text-sm font-medium">
                <span>Only after</span>
                <CannedResponseSelect
                  value={form.followsId ?? NO_PARENT}
                  onValueChange={(value) =>
                    onChange({ ...form, followsId: !value || value === NO_PARENT ? null : value })
                  }
                  items={followOptions(records, form.siteId, form.id)}
                  label="Only after"
                />
                <span className="text-mute text-xs font-normal">
                  For answers like #der_yes. The assistant sends this only as the reply to the
                  script chosen here; without one, a bare yes or no never selects it.
                </span>
              </div>
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
              <label
                htmlFor="canned-response-bot"
                className="border-line bg-ice text-ink flex items-center justify-between gap-3 rounded-[8px] border px-3 py-2.5 text-sm font-medium"
              >
                <span>
                  <span className="block">Available to the bot</span>
                  <span className="text-mute block text-xs font-normal">
                    Leave off for greetings, idle nags, and discount codes.
                  </span>
                </span>
                <Switch
                  id="canned-response-bot"
                  checked={form.botEligible}
                  onCheckedChange={(botEligible) => onChange({ ...form, botEligible })}
                  aria-label="Available to the bot"
                />
              </label>
              {form.botEligible && blockedReason ? (
                <p className="text-ember -mt-2 text-xs" role="note">
                  The assistant will not use this wording yet. {blockedReason}
                </p>
              ) : null}
              <label
                htmlFor="canned-response-handoff"
                className="border-line bg-ice text-ink flex items-center justify-between gap-3 rounded-[8px] border px-3 py-2.5 text-sm font-medium"
              >
                <span>
                  <span className="block">Connect a specialist after sending</span>
                  <span className="text-mute block text-xs font-normal">
                    For scripts that promise to document or route something.
                  </span>
                </span>
                <Switch
                  id="canned-response-handoff"
                  checked={form.handsOff}
                  onCheckedChange={(handsOff) => onChange({ ...form, handsOff })}
                  aria-label="Connect a specialist after sending"
                />
              </label>
              <FieldError>{formError || undefined}</FieldError>
            </div>
            <DialogFooter className="flex-row items-center justify-end gap-2">
              <Button type="button" variant="outline" size="lg" onClick={onRequestClose}>
                Cancel
              </Button>
              <Button type="submit" variant="default" size="lg" disabled={submitting}>
                {submitting ? <Spinner data-icon="inline-start" /> : null}
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
          {deleting ? <Spinner data-icon="inline-start" /> : null}
          {deleting ? "Removing…" : "Remove response"}
        </Button>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
)
