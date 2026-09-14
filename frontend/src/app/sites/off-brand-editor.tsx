"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import { staffWrite, type SiteRecord } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

const FIELD =
  "border-line bg-ice text-ink focus-visible:ring-steel mt-1.5 w-full rounded-[8px] border px-3 py-2.5 text-sm outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-60"
const LABEL = "text-mute text-[10px] font-bold tracking-[0.12em] uppercase"

type OffBrandEditorProps = {
  site: SiteRecord
  isAdmin: boolean
  onError: (message: string | null) => void
  onSaved: (site: SiteRecord) => void
}

export const OffBrandEditor = ({ site, isAdmin, onError, onSaved }: OffBrandEditorProps) => {
  const [text, setText] = useState((site.off_brand_blocklist ?? []).join("\n"))
  const [savedNotice, setSavedNotice] = useState<string | null>(null)

  const handleChange = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setText(event.target.value)
    setSavedNotice(null)
  }, [])

  const handleSave = useCallback(async () => {
    const items = text
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
    const response = await staffWrite(`/api/sites/${site.id}/off-brand-list`, "PATCH", {
      items,
    })
    if (!response.ok) {
      onError("Could not save the off-brand list. Check each line and try again.")
      return
    }
    onError(null)
    const next = (await response.json()) as SiteRecord
    onSaved(next)
    setText((next.off_brand_blocklist ?? []).join("\n"))
    setSavedNotice("Off-brand list saved.")
  }, [onError, onSaved, site.id, text])

  return (
    <div className="border-line mt-6 border-t pt-5">
      <p className={LABEL}>Guardrails</p>
      <h3 className="text-navy mt-1 text-sm font-extrabold">Off-brand blocklist</h3>
      <p className="text-mute mt-2 text-xs leading-5">
        One competitor or unrelated brand per line. Mentions without matching knowledge return an
        out-of-scope reply.
      </p>
      <label className={LABEL} htmlFor={`off-brand-${site.id}`}>
        Brands
      </label>
      <Textarea
        id={`off-brand-${site.id}`}
        value={text}
        disabled={!isAdmin}
        onChange={handleChange}
        className={`${FIELD} font-mono text-xs leading-6`}
        rows={4}
        aria-label="Off-brand blocklist"
      />
      {savedNotice ? (
        <output className="text-steel mt-2 block text-xs">{savedNotice}</output>
      ) : null}
      {isAdmin ? (
        <div className="mt-3 flex justify-end">
          <Button
            type="button"
            onClick={handleSave}
            className="bg-navy text-primary-foreground hover:bg-navy-deep focus-visible:ring-steel cursor-pointer rounded-[8px] px-4 py-2.5 text-sm font-bold focus-visible:ring-2 focus-visible:outline-none"
          >
            Save blocklist
          </Button>
        </div>
      ) : null}
    </div>
  )
}
