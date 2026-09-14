"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import { staffWrite, type SiteRecord } from "@/components/admin/staff-api"

import { useLeaveGuard } from "./sites-form"
import { useSiteValidation } from "./use-site-validation"

// oxlint-disable-next-line max-lines-per-function
export const useAddSiteForm = (
  isAdmin: boolean,
  onClose: () => void,
  onCreated: (site: SiteRecord) => void,
  onError: (message: string | null) => void,
) => {
  const [name, setName] = useState("")
  const [greeting, setGreeting] = useState("")
  const [privacyUrl, setPrivacyUrl] = useState("")
  const [originsText, setOriginsText] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const dirty =
    name.trim().length > 0 ||
    greeting.trim().length > 0 ||
    privacyUrl.trim().length > 0 ||
    originsText.trim().length > 0
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
  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) {
        requestClose()
      }
    },
    [requestClose],
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
    const origins = originsText
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
    const response = await staffWrite("/api/sites", "POST", {
      name,
      greeting,
      privacy_url: privacyUrl,
      origins,
    })
    if (!response.ok) {
      onError("Could not create the site. Check the privacy URL and origins.")
      return
    }
    onError(null)
    onCreated((await response.json()) as SiteRecord)
  }, [greeting, isAdmin, name, onCreated, onError, originsText, privacyUrl, validate])

  return {
    name,
    greeting,
    privacyUrl,
    originsText,
    errors,
    leaveOpen,
    requestClose,
    handleStay,
    handleLeave,
    handleName,
    handleGreeting,
    handlePrivacy,
    handleOrigins,
    handleNameBlur,
    handlePrivacyBlur,
    handleOriginsBlur,
    handleOpenChange,
    handleSubmit,
  }
}
