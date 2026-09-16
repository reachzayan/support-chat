"use client"

import { useCallback, type Dispatch, type SetStateAction } from "react"

import {
  extraOriginsError,
  httpUrlError,
  originsError,
  requiredError,
  websiteUrlError,
} from "@/lib/validation"

type SetErrors = Dispatch<SetStateAction<Record<string, string>>>

const updateError = (setErrors: SetErrors, key: string, error: string | null) => {
  setErrors((current) => {
    if (error) return { ...current, [key]: error }
    const next = { ...current }
    delete next[key]
    return next
  })
}

export const useSiteValidation = (
  name: string,
  privacyUrl: string,
  originsText: string,
  websiteUrl: string,
  websiteUrlRequired: boolean,
  setErrors: SetErrors,
  originsRequired = true,
) => {
  const handleNameBlur = useCallback(
    () => updateError(setErrors, "name", requiredError("Name", name)),
    [name, setErrors],
  )
  const handlePrivacyBlur = useCallback(
    () => updateError(setErrors, "privacyUrl", httpUrlError(privacyUrl)),
    [privacyUrl, setErrors],
  )
  const handleOriginsBlur = useCallback(
    () =>
      updateError(
        setErrors,
        "origins",
        originsRequired ? originsError(originsText) : extraOriginsError(originsText),
      ),
    [originsRequired, originsText, setErrors],
  )
  const handleWebsiteUrlBlur = useCallback(
    () => updateError(setErrors, "websiteUrl", websiteUrlError(websiteUrl, websiteUrlRequired)),
    [websiteUrl, websiteUrlRequired, setErrors],
  )
  const validate = useCallback(
    () => ({
      name: requiredError("Name", name),
      privacyUrl: httpUrlError(privacyUrl),
      origins: originsRequired ? originsError(originsText) : extraOriginsError(originsText),
      websiteUrl: websiteUrlError(websiteUrl, websiteUrlRequired),
    }),
    [name, originsRequired, originsText, privacyUrl, websiteUrl, websiteUrlRequired],
  )

  return { handleNameBlur, handlePrivacyBlur, handleOriginsBlur, handleWebsiteUrlBlur, validate }
}
