const STAFF_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const parseStaffEmail = (raw: string): string | null => {
  const normalized = raw.trim().toLowerCase()
  if (!STAFF_EMAIL.test(normalized)) {
    return null
  }
  return normalized
}
