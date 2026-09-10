export const visitorStorageKey = (siteKey: string) => `supportchat.visitor.${siteKey}`

export const readResumeToken = (siteKey: string): string | null => {
  try {
    return window.localStorage.getItem(visitorStorageKey(siteKey))
  } catch {
    return null
  }
}

export const writeResumeToken = (siteKey: string, token: string): void => {
  try {
    window.localStorage.setItem(visitorStorageKey(siteKey), token)
  } catch {
    return
  }
}

export const clearResumeToken = (siteKey: string): void => {
  try {
    window.localStorage.removeItem(visitorStorageKey(siteKey))
  } catch {
    return
  }
}
