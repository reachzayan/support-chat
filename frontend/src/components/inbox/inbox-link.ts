// Keep a notification deep link aligned with subsequent inbox navigation.
export const updateInboxLink = (conversationId: string | null) => {
  const url = new URL(window.location.href)
  if (!url.searchParams.has("conversation")) return
  if (conversationId === url.searchParams.get("conversation")) return
  if (conversationId) url.searchParams.set("conversation", conversationId)
  else url.searchParams.delete("conversation")
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`)
}
