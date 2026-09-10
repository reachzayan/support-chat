const NAVY = "#0B2347"
const STEEL = "#2456A0"
const PAPER = "#FFFFFF"
const INK = "#0D1F3A"

export const mountLauncher = (doc: Document, handleOpen: () => void): HTMLButtonElement => {
  const style = doc.createElement("style")
  style.textContent =
    "[data-supportchat-launcher]{transition:transform 180ms ease,box-shadow 180ms ease}[data-supportchat-launcher]:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(11,35,71,0.4)}[data-supportchat-launcher]:active{transform:translateY(0) scale(.96)}[data-supportchat-launcher]:focus-visible{outline:2px solid #2456A0;outline-offset:2px}@media (prefers-reduced-motion: reduce){[data-supportchat-launcher]{transition:none}}"
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
    "border:0",
    "border-radius:50%",
    `background:${NAVY}`,
    "cursor:pointer",
    "z-index:2147483646",
    "touch-action:manipulation",
    "display:flex",
    "align-items:center",
    "justify-content:center",
    "box-shadow:0 8px 24px rgba(11,35,71,0.35)",
  ].join(";")
  const icon = doc.createElementNS("http://www.w3.org/2000/svg", "svg")
  icon.setAttribute("viewBox", "0 0 24 24")
  icon.setAttribute("width", "28")
  icon.setAttribute("height", "28")
  icon.setAttribute("aria-hidden", "true")
  icon.setAttribute("focusable", "false")
  const bubble = doc.createElementNS("http://www.w3.org/2000/svg", "path")
  bubble.setAttribute(
    "d",
    "M5 4h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-6l-4 3v-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  )
  bubble.setAttribute("fill", PAPER)
  icon.appendChild(bubble)
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
