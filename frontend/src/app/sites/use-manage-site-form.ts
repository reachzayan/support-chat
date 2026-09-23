"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import {
  canonicalizeHttpUrl,
  canonicalizeHttpsUrl,
  canonicalizeOriginLines,
} from "@/lib/validation"

import { saveManageSite } from "./manage-site-save"
import { useLeaveGuard } from "./sites-form"
import { useSiteValidation } from "./use-site-validation"

const isManageSiteDirty = (
  site: SiteRecord,
  fields: {
    name: string
    greeting: string
    privacyUrl: string
    websiteUrl: string
    originsText: string
    contactInfoText: string
    windowHours: number
  },
) =>
  fields.name !== site.name ||
  fields.greeting !== site.greeting ||
  fields.privacyUrl !== site.privacy_url ||
  fields.websiteUrl !== (site.website_url ?? "") ||
  fields.originsText !== site.origins.join("\n") ||
  fields.contactInfoText !== (site.contact_info ?? []).join("\n") ||
  fields.windowHours !== (site.callback_window_hours ?? 24)

// oxlint-disable-next-line max-lines-per-function
export const useManageSiteForm = (
  site: SiteRecord,
  onClose: () => void,
  onSaved: (site: SiteRecord) => void,
  onError: (message: string | null) => void,
) => {
  const [name, setName] = useState(site.name)
  const [greeting, setGreeting] = useState(site.greeting)
  const [privacyUrl, setPrivacyUrl] = useState(site.privacy_url)
  const [websiteUrl, setWebsiteUrl] = useState(site.website_url ?? "")
  const [originsText, setOriginsText] = useState(site.origins.join("\n"))
  const [contactInfoText, setContactInfoText] = useState((site.contact_info ?? []).join("\n"))
  const [windowHours, setWindowHours] = useState(site.callback_window_hours ?? 24)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const dirty = isManageSiteDirty(site, {
    name,
    greeting,
    privacyUrl,
    websiteUrl,
    originsText,
    contactInfoText,
    windowHours,
  })

  const { leaveOpen, requestClose, handleStay, handleLeave } = useLeaveGuard(dirty, onClose)
  const { handleNameBlur, handlePrivacyBlur, handleOriginsBlur, handleWebsiteUrlBlur, validate } =
    useSiteValidation(name, privacyUrl, originsText, websiteUrl, false, setErrors)

  const handlePrivacyFieldBlur = useCallback(() => {
    const canonical = canonicalizeHttpUrl(privacyUrl)
    if (canonical) setPrivacyUrl(canonical)
    handlePrivacyBlur()
  }, [handlePrivacyBlur, privacyUrl])
  const handleWebsiteUrlFieldBlur = useCallback(() => {
    const canonical = canonicalizeHttpsUrl(websiteUrl)
    if (canonical) setWebsiteUrl(canonical)
    handleWebsiteUrlBlur()
  }, [handleWebsiteUrlBlur, websiteUrl])
  const handleOriginsFieldBlur = useCallback(() => {
    setOriginsText(canonicalizeOriginLines(originsText).join("\n"))
    handleOriginsBlur()
  }, [handleOriginsBlur, originsText])
  const handleName = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setName(event.target.value)
  }, [])
  const handleGreeting = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setGreeting(event.target.value)
  }, [])
  const handlePrivacy = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setPrivacyUrl(event.target.value)
  }, [])
  const handleWebsiteUrl = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setWebsiteUrl(event.target.value)
  }, [])
  const handleOrigins = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setOriginsText(event.target.value)
  }, [])
  const handleContactInfo = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setContactInfoText(event.target.value)
  }, [])
  const handleWindow = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const next = Number(event.target.value)
    if (Number.isNaN(next)) {
      return
    }
    setWindowHours(Math.min(168, Math.max(1, next)))
  }, [])
  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) {
        requestClose()
      }
    },
    [requestClose],
  )
  const handleSave = useCallback(async () => {
    const nextErrors = validate()
    const visibleErrors = Object.fromEntries(
      Object.entries(nextErrors).filter((entry): entry is [string, string] => entry[1] !== null),
    )
    setErrors(visibleErrors)
    if (Object.keys(visibleErrors).length > 0) {
      return
    }
    await saveManageSite(
      site.id,
      { name, greeting, privacyUrl, websiteUrl, originsText, contactInfoText, windowHours },
      onSaved,
      onError,
    )
  }, [
    contactInfoText,
    greeting,
    name,
    onError,
    onSaved,
    originsText,
    privacyUrl,
    site.id,
    validate,
    websiteUrl,
    windowHours,
  ])
  return {
    name,
    greeting,
    privacyUrl,
    websiteUrl,
    originsText,
    contactInfoText,
    windowHours,
    errors,
    leaveOpen,
    requestClose,
    handleStay,
    handleLeave,
    handleName,
    handleGreeting,
    handlePrivacy,
    handleWebsiteUrl,
    handleOrigins,
    handleContactInfo,
    handleWindow,
    handleNameBlur,
    handlePrivacyBlur: handlePrivacyFieldBlur,
    handleWebsiteUrlBlur: handleWebsiteUrlFieldBlur,
    handleOriginsBlur: handleOriginsFieldBlur,
    handleOpenChange,
    handleSave,
  }
}
