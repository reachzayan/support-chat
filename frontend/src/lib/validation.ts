const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const HAS_SCHEME = /^[a-zA-Z][a-zA-Z0-9+.-]*:/

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

type ParsedHttpUrl = {
  protocol: "http:" | "https:"
  host: string
  port: string
  pathname: string
  search: string
}

const hostWithoutWww = (hostname: string) => {
  const host = hostname.toLowerCase()
  return host.startsWith("www.") ? host.slice(4) : host
}

const parseFlexibleHttpUrl = (value: string): ParsedHttpUrl | null => {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }
  try {
    const url = new URL(HAS_SCHEME.test(trimmed) ? trimmed : `https://${trimmed}`)
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null
    }
    if (url.username || url.password) {
      return null
    }
    const host = hostWithoutWww(url.hostname)
    if (!host) {
      return null
    }
    return {
      protocol: url.protocol,
      host,
      port: url.port,
      pathname: url.pathname,
      search: url.search,
    }
  } catch {
    return null
  }
}

const originPath = (pathname: string) => pathname === "" || pathname === "/"

const dropDefaultPort = (protocol: "http:" | "https:", port: string) => {
  if (!port) {
    return ""
  }
  if (protocol === "https:" && port === "443") {
    return ""
  }
  if (protocol === "http:" && port === "80") {
    return ""
  }
  return `:${port}`
}

const storedPath = (pathname: string) => {
  if (originPath(pathname)) {
    return ""
  }
  return pathname.replace(/\/+$/, "")
}

export const canonicalizeHttpsUrl = (value: string) => {
  const parsed = parseFlexibleHttpUrl(value)
  if (!parsed) {
    return null
  }
  const port = dropDefaultPort("https:", parsed.port === "80" ? "" : parsed.port)
  return `https://${parsed.host}${port}${storedPath(parsed.pathname)}${parsed.search}`
}

export const canonicalizeHttpUrl = (value: string) => {
  const parsed = parseFlexibleHttpUrl(value)
  if (!parsed) {
    return null
  }
  const protocol = parsed.protocol === "http:" ? "http:" : "https:"
  const port = dropDefaultPort(protocol, parsed.port)
  return `${protocol}//${parsed.host}${port}${storedPath(parsed.pathname)}${parsed.search}`
}

export const canonicalizeOrigin = (value: string) => {
  const parsed = parseFlexibleHttpUrl(value)
  if (!parsed || !originPath(parsed.pathname) || parsed.search) {
    return null
  }
  const protocol = parsed.protocol === "http:" ? "http:" : "https:"
  const port = dropDefaultPort(protocol, parsed.port)
  return `${protocol}//${parsed.host}${port}`
}

export const httpUrlError = (value: string) => {
  if (value.trim() === "") {
    return "Privacy URL is required."
  }
  return canonicalizeHttpUrl(value) ? null : "Enter a valid URL."
}

const isValidOrigin = (origin: string) => canonicalizeOrigin(origin) !== null

export const originFromWebsiteUrl = (value: string) => {
  const canonical = canonicalizeHttpsUrl(value)
  if (!canonical) {
    return null
  }
  return new URL(canonical).origin
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
  return canonicalizeHttpsUrl(trimmed) ? null : "Use a valid https:// URL."
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
    if (!canonicalizeHttpsUrl(candidate)) {
      return "Use one valid https:// URL per line."
    }
  }
  return null
}

export const canonicalizeHttpsLines = (value: string) =>
  value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => canonicalizeHttpsUrl(line))
    .filter((line): line is string => line !== null)

export const canonicalizeOriginLines = (value: string) =>
  value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => canonicalizeOrigin(line) ?? line)
