const INK = "#0D1F3A"
const PAPER = "#FFFFFF"
const STEEL = "#2456A0"

export const mountLauncher = (
  doc: Document,
  handleOpen: () => void,
  _widgetOrigin: string,
): HTMLButtonElement => {
  const style = doc.createElement("style")
  style.textContent =
    "[data-supportchat-launcher]{transition:transform 180ms ease,box-shadow 180ms ease}[data-supportchat-launcher]:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(11,35,71,0.28)}[data-supportchat-launcher]:active{transform:translateY(0) scale(.96)}[data-supportchat-launcher]:focus-visible{outline:2px solid #2456A0;outline-offset:2px}@media (prefers-reduced-motion: reduce){[data-supportchat-launcher]{transition:none}}"
  doc.head.appendChild(style)

  const button = doc.createElement("button")
  button.type = "button"
  button.setAttribute("aria-label", "Open chat")
  button.setAttribute("data-supportchat-launcher", "")
  button.style.cssText = [
    "position:fixed",
    "right:24px",
    "bottom:24px",
    "width:56px",
    "height:56px",
    "padding:0",
    "border:0",
    "border-radius:50%",
    "background:#0B2347",
    "cursor:pointer",
    "z-index:2147483646",
    "touch-action:manipulation",
    "display:flex",
    "align-items:center",
    "justify-content:center",
    "overflow:visible",
    "box-shadow:0 8px 24px rgba(11,35,71,0.28)",
  ].join(";")
  const icon = doc.createElement("span")
  icon.textContent = "Chat"

  icon.setAttribute("aria-hidden", "true")


  icon.style.cssText =
    "color:white;font:600 12px/1 system-ui,sans-serif"
  button.appendChild(icon)
  button.addEventListener("click", handleOpen)
  doc.body.appendChild(button)
  return button
}

export const showHostError = (doc: Document, handleRetry: () => void): HTMLElement => {
  const existing = doc.querySelector("[data-supportchat-error]")
  if (existing instanceof HTMLElement) {
    existing.hidden = false
    return existing
  }
  const panel = doc.createElement("div")
  panel.setAttribute("data-supportchat-error", "")
  panel.setAttribute("role", "alert")
  panel.style.cssText = [
    "position:fixed",
    "right:24px",
    "bottom:96px",
    "width:280px",
    `background:${PAPER}`,
    `color:${INK}`,
    "border-radius:8px",
    "padding:16px",
    "z-index:2147483646",
    "font:14px/1.4 system-ui,sans-serif",
  ].join(";")
  const message = doc.createElement("p")
  message.textContent = "Chat is not available on this page"
  const retry = doc.createElement("button")
  retry.type = "button"
  retry.setAttribute("aria-label", "Retry")
  retry.textContent = "Retry"
  retry.style.cssText = `margin-top:12px;background:${STEEL};color:${PAPER};border:0;border-radius:8px;padding:8px 12px;cursor:pointer`
  retry.addEventListener("click", handleRetry)
  panel.append(message, retry)
  doc.body.appendChild(panel)
  return panel
}

export const hideHostError = (doc: Document) => {
  const existing = doc.querySelector("[data-supportchat-error]")
  if (existing instanceof HTMLElement) {
    existing.hidden = true
  }
}

export const setLauncherUnread = (button: HTMLButtonElement, count: number) => {
  let badge = button.querySelector<HTMLSpanElement>("[data-supportchat-unread]")
  if (!badge) {
    badge = button.ownerDocument.createElement("span")
    badge.setAttribute("data-supportchat-unread", "")
    badge.setAttribute("aria-hidden", "true")
    badge.style.cssText =
      "position:absolute;top:-3px;right:-3px;min-width:22px;height:22px;padding:0 5px;box-sizing:border-box;border-radius:999px;background:#C45516;color:#fff;border:2px solid #fff;font:bold 11px/18px system-ui,sans-serif;text-align:center;font-variant-numeric:tabular-nums;pointer-events:none"
    button.appendChild(badge)
  }
  badge.style.display = count > 0 ? "block" : "none"
  badge.textContent = count > 0 ? (count > 99 ? "99+" : String(count)) : ""
  button.setAttribute(
    "aria-label",
    count > 0 ? `Open chat, ${count} unread ${count === 1 ? "message" : "messages"}` : "Open chat",
  )
}
