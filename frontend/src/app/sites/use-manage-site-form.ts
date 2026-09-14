"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"

import { copyManageSnippet, saveManageSite } from "./manage-site-save"
import { useLeaveGuard } from "./sites-form"
import { useSiteValidation } from "./use-site-validation"

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
  const [originsText, setOriginsText] = useState(site.origins.join("\n"))
  const [windowHours, setWindowHours] = useState(site.callback_window_hours ?? 24)
  const [copyNotice, setCopyNotice] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const dirty =
    name !== site.name ||
    greeting !== site.greeting ||
    privacyUrl !== site.privacy_url ||
    originsText !== site.origins.join("\n") ||
    windowHours !== (site.callback_window_hours ?? 24)

  const { leaveOpen, requestClose, handleStay, handleLeave } = useLeaveGuard(dirty, onClose)
  const { handleNameBlur, handlePrivacyBlur, handleOriginsBlur, validate } = useSiteValidation(
    name,
    privacyUrl,
    originsText,
    setErrors,
  )

  const handleName = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setName(event.target.value)
  }, [])
  const handleGreeting = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setGreeting(event.target.value)
  }, [])
  const handlePrivacy = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setPrivacyUrl(event.target.value)
  }, [])
  const handleOrigins = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setOriginsText(event.target.value)
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
      { name, greeting, privacyUrl, originsText, windowHours },
      onSaved,
      onError,
    )
  }, [greeting, name, onError, onSaved, originsText, privacyUrl, site.id, validate, windowHours])
  const handleCopy = useCallback(async () => {
    await copyManageSnippet(site.snippet, setCopyNotice)
  }, [site.snippet])

  return {
    name,
    greeting,
    privacyUrl,
    originsText,
    windowHours,
    errors,
    copyNotice,
    leaveOpen,
    requestClose,
    handleStay,
    handleLeave,
    handleName,
    handleGreeting,
    handlePrivacy,
    handleOrigins,
    handleWindow,
    handleNameBlur,
    handlePrivacyBlur,
    handleOriginsBlur,
    handleOpenChange,
    handleSave,
    handleCopy,
  }
}
