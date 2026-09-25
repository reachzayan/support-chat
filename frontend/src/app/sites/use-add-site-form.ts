"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import { staffWrite, type SiteRecord } from "@/components/admin/staff-api"
import {
  canonicalizeHttpUrl,
  canonicalizeHttpsUrl,
  canonicalizeOriginLines,
  originFromWebsiteUrl,
} from "@/lib/validation"

import { useLeaveGuard } from "./sites-form"
import { useSiteValidation } from "./use-site-validation"

const linesFromText = (text: string) =>
  text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)

const mergedOrigins = (websiteUrl: string, originsText: string) => {
  const locked = originFromWebsiteUrl(websiteUrl)
  const extra = canonicalizeOriginLines(originsText)
  if (locked === null) {
    return extra
  }
  return [locked, ...extra.filter((origin) => origin !== locked)]
}

// oxlint-disable-next-line max-lines-per-function
export const useAddSiteForm = (
  isAdmin: boolean,
  onClose: () => void,
  onCreated: (site: SiteRecord) => void,
  onSaved: (site: SiteRecord) => void,
  onError: (message: string | null) => void,
) => {
  const [name, setName] = useState("")
  const [greeting, setGreeting] = useState("")
  const [privacyUrl, setPrivacyUrl] = useState("")
  const [websiteUrl, setWebsiteUrl] = useState("")
  const [originsText, setOriginsText] = useState("")
  const [contactInfoText, setContactInfoText] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [created, setCreated] = useState<SiteRecord | null>(null)
  const [checking, setChecking] = useState(false)
  const lockedOrigin = originFromWebsiteUrl(websiteUrl)
  const dirty =
    created === null &&
    (name.trim().length > 0 ||
      greeting.trim().length > 0 ||
      privacyUrl.trim().length > 0 ||
      websiteUrl.trim().length > 0 ||
      originsText.trim().length > 0 ||
      contactInfoText.trim().length > 0)
  const { leaveOpen, requestClose, handleStay, handleLeave } = useLeaveGuard(dirty, onClose)
  const { handleNameBlur, handlePrivacyBlur, handleOriginsBlur, handleWebsiteUrlBlur, validate } =
    useSiteValidation(name, privacyUrl, originsText, websiteUrl, true, setErrors, false)

  const handleName = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setName(event.target.value)
  }, [])
  const handleGreeting = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setGreeting(event.target.value)
  }, [])
  const handlePrivacy = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setPrivacyUrl(event.target.value)
  }, [])
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
  const handleWebsiteUrl = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setWebsiteUrl(event.target.value)
  }, [])
  const handleOrigins = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setOriginsText(event.target.value)
  }, [])
  const handleContactInfo = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setContactInfoText(event.target.value)
  }, [])
  const handleDone = useCallback(() => {
    onClose()
  }, [onClose])
  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) {
        if (created) {
          onClose()
          return
        }
        requestClose()
      }
    },
    [created, onClose, requestClose],
  )
  const handleSubmit = useCallback(async () => {
    if (!isAdmin) {
      return
    }
    const nextErrors = validate()
    const visibleErrors = Object.fromEntries(
      Object.entries(nextErrors).filter((entry): entry is [string, string] => entry[1] !== null),
    )
    setErrors(visibleErrors)
    if (Object.keys(visibleErrors).length > 0) {
      return
    }
    const response = await staffWrite("/api/sites", "POST", {
      name,
      greeting,
      privacy_url: canonicalizeHttpUrl(privacyUrl) ?? privacyUrl,
      origins: mergedOrigins(websiteUrl, originsText),
      website_url: canonicalizeHttpsUrl(websiteUrl) ?? websiteUrl,
      contact_info: linesFromText(contactInfoText),
    })
    if (!response.ok) {
      onError("Could not create the site. Check the privacy URL and origins.")
      return
    }
    const site = (await response.json()) as SiteRecord
    onError(null)
    setCreated(site)
    onCreated(site)
  }, [
    contactInfoText,
    greeting,
    isAdmin,
    name,
    onCreated,
    onError,
    originsText,
    privacyUrl,
    validate,
    websiteUrl,
  ])
  const handleCheckInstall = useCallback(async () => {
    if (created === null) {
      return
    }
    setChecking(true)
    try {
      const response = await staffWrite(`/api/sites/${created.id}/check-install`, "POST", {})
      if (!response.ok) {
        onError("Could not recheck the widget install status.")
        return
      }
      const next = (await response.json()) as SiteRecord
      onError(null)
      setCreated(next)
      onSaved(next)
    } catch {
      onError("Could not recheck the widget install status.")
    } finally {
      setChecking(false)
    }
  }, [created, onError, onSaved])
  return {
    name,
    greeting,
    privacyUrl,
    websiteUrl,
    originsText,
    contactInfoText,
    lockedOrigin,
    errors,
    created,
    checking,
    leaveOpen,
    requestClose,
    handleStay,
    handleLeave,
    handleDone,
    handleName,
    handleGreeting,
    handlePrivacy,
    handleWebsiteUrl,
    handleOrigins,
    handleContactInfo,
    handleNameBlur,
    handlePrivacyBlur: handlePrivacyFieldBlur,
    handleWebsiteUrlBlur: handleWebsiteUrlFieldBlur,
    handleOriginsBlur: handleOriginsFieldBlur,
    handleOpenChange,
    handleSubmit,
    handleCheckInstall,
  }
}
