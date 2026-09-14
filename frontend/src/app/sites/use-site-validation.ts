"use client"

import { useCallback, type Dispatch, type SetStateAction } from "react"

import { httpUrlError, originsError, requiredError } from "@/lib/validation"

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
  setErrors: SetErrors,
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
    () => updateError(setErrors, "origins", originsError(originsText)),
    [originsText, setErrors],
  )
  const validate = useCallback(
    () => ({
      name: requiredError("Name", name),
      privacyUrl: httpUrlError(privacyUrl),
      origins: originsError(originsText),
    }),
    [name, originsText, privacyUrl],
  )

  return { handleNameBlur, handlePrivacyBlur, handleOriginsBlur, validate }
}
