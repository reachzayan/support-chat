const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const requiredError = (label: string, value: string) =>
  value.trim() === "" ? `${label} is required.` : null

export const emailError = (value: string) => {
  if (value.trim() === "") {
    return "Email is required."
  }
  return EMAIL_PATTERN.test(value.trim()) ? null : "Enter a valid email address."
}

export const phoneError = (value: string) => {
  if (value.trim() === "") {
    return null
  }
  const digits = value.replace(/\D/g, "")
  return digits.length >= 7 ? null : "Enter a valid phone number."
}

export const httpUrlError = (value: string) => {
  if (value.trim() === "") {
    return "Privacy URL is required."
  }
  try {
    const url = new URL(value.trim())
    return url.protocol === "http:" || url.protocol === "https:"
      ? null
      : "Use an http:// or https:// URL."
  } catch {
    return "Enter a valid URL."
  }
}

const isValidOrigin = (origin: string) => {
  try {
    const url = new URL(origin)
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      url.pathname === "/" &&
      !url.search &&
      !url.hash &&
      !url.username &&
      !url.password
    )
  } catch {
    return false
  }
}

export const originFromWebsiteUrl = (value: string) => {
  try {
    const url = new URL(value.trim())
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null
    }
    if (url.username || url.password) {
      return null
    }
    return url.origin
  } catch {
    return null
  }
}

export const originsError = (value: string) => {
  const origins = value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
  if (origins.length === 0) {
    return "Add at least one approved origin."
  }
  for (const origin of origins) {
    if (!isValidOrigin(origin)) {
      return "Use one http:// or https:// origin per line."
    }
  }
  return null
}

export const extraOriginsError = (value: string) => {
  const origins = value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
  if (origins.length === 0) {
    return null
  }
  for (const origin of origins) {
    if (!isValidOrigin(origin)) {
      return "Use one http:// or https:// origin per line."
    }
  }
  return null
}

export const websiteUrlError = (value: string, required: boolean) => {
  const trimmed = value.trim()
  if (trimmed === "") {
    return required ? "Website URL is required." : null
  }
  try {
    return new URL(trimmed).protocol === "https:" ? null : "Use a valid https:// URL."
  } catch {
    return "Use a valid https:// URL."
  }
}

export const httpsUrlsError = (value: string) => {
  const urls = value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
  if (urls.length === 0) {
    return "Add at least one page URL."
  }
  for (const candidate of urls) {
    try {
      if (new URL(candidate).protocol !== "https:") {
        return "Use one valid https:// URL per line."
      }
    } catch {
      return "Use one valid https:// URL per line."
    }
  }
  return null
}
