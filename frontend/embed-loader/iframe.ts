import { parseWidgetToHost, type HostToWidget } from "../src/lib/postmessage"
import { sanitizePageUrl, sanitizeTitle } from "./sanitize"

type PanelState = {
  widgetOrigin: string
  iframe: HTMLIFrameElement | null
  pendingResume: string | null
  bootstrap: HostToWidget | null
  launcher: HTMLButtonElement
}

// Phones (and landscape phones) get a full-viewport sheet instead of the floating card.
export const SHEET_QUERY = "(max-width: 640px), (max-height: 500px) and (max-width: 932px)"

const SHEET_STYLE = [
  "top:var(--supportchat-vvt,0px)!important",
  "left:0!important",
  "right:0!important",
  "bottom:auto!important",
  "width:100%!important",
  "max-width:none!important",
  "height:100vh!important",
  "height:var(--supportchat-vvh,100dvh)!important",
  "max-height:none!important",
  "border-radius:0!important",
  "box-shadow:none!important",
  "transform-origin:bottom center",
].join(";")

export const isSheetLayout = (win: Window) => {
  try {
    return win.matchMedia(SHEET_QUERY).matches
  } catch {
    return false
  }
}

const PLACEHOLDER_STYLE = [
  `@media ${SHEET_QUERY}{[data-supportchat-placeholder]{${SHEET_STYLE}}}`,
  "[data-supportchat-placeholder]{position:fixed;right:24px;bottom:24px;width:420px;height:680px;max-width:calc(100vw - 32px);max-height:calc(100vh - 32px);box-sizing:border-box;border-radius:30px;background:#F4F8FF;box-shadow:0 20px 60px rgba(13,31,58,0.22);z-index:2147483646;display:flex;flex-direction:column;overflow:hidden;font:14px/1.4 system-ui,sans-serif;color:#0B2347}",
  "[data-supportchat-placeholder][hidden]{display:none}",
  "[data-supportchat-placeholder] .c365-head{display:flex;align-items:center;gap:12px;padding:18px 20px;background:#0B2347}",
  "[data-supportchat-placeholder] .c365-dot{width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.18)}",
  "[data-supportchat-placeholder] .c365-line{height:12px;border-radius:6px;background:rgba(255,255,255,.28);width:120px}",
  "[data-supportchat-placeholder] .c365-body{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px}",
  "[data-supportchat-placeholder] .c365-spin{width:32px;height:32px;border-radius:50%;border:3px solid rgba(196,85,22,.25);border-top-color:#C45516;animation:chat365-spin .8s linear infinite}",
  "[data-supportchat-placeholder] .c365-bar{height:12px;border-radius:6px;background:#DCE6F5;width:70%}",
  "@keyframes chat365-spin{to{transform:rotate(360deg)}}",
  "@media (prefers-reduced-motion: reduce){[data-supportchat-placeholder] .c365-spin{animation:none;border-color:#C45516}}",
].join("")

const PANEL_STYLE = [
  PLACEHOLDER_STYLE,
  `@media ${SHEET_QUERY}{[data-supportchat-panel]{${SHEET_STYLE}}}`,
  "[data-supportchat-panel]{transform-origin:bottom right;transition:opacity 220ms ease,transform 300ms cubic-bezier(0.22,1,0.36,1),border-radius 300ms cubic-bezier(0.22,1,0.36,1);will-change:transform,opacity}",
  "@media (prefers-reduced-motion: reduce){[data-supportchat-panel]{transition:none}}",
].join("")

const SCROLL_LOCK_ATTR = "data-supportchat-scroll-lock"

// Keeps the host page from scrolling behind a full-screen sheet; restores the host's own value.
export const setHostScrollLock = (doc: Document, locked: boolean) => {
  const root = doc.documentElement
  if (locked) {
    if (root.hasAttribute(SCROLL_LOCK_ATTR)) return
    root.setAttribute(SCROLL_LOCK_ATTR, root.style.overflow)
    root.style.overflow = "hidden"
    return
  }
  const previous = root.getAttribute(SCROLL_LOCK_ATTR)
  if (previous === null) return
  root.removeAttribute(SCROLL_LOCK_ATTR)
  root.style.overflow = previous
}

// Tracks the visual viewport so the on-screen keyboard never covers the composer on a sheet.
export const syncSheetViewport = (win: Window, iframe: HTMLIFrameElement | null) => {
  if (iframe === null) return
  const viewport = win.visualViewport
  if (!isSheetLayout(win) || viewport === null || viewport === undefined) {
    iframe.style.removeProperty("--supportchat-vvh")
    iframe.style.removeProperty("--supportchat-vvt")
    return
  }
  iframe.style.setProperty("--supportchat-vvh", `${Math.round(viewport.height)}px`)
  iframe.style.setProperty("--supportchat-vvt", `${Math.round(viewport.offsetTop)}px`)
}

const ensurePanelStyle = (doc: Document) => {
  if (doc.querySelector("[data-supportchat-panel-style]") !== null) {
    return
  }
  const style = doc.createElement("style")
  style.setAttribute("data-supportchat-panel-style", "")
  style.textContent = PANEL_STYLE
  doc.head.appendChild(style)
}

// Host-side skeleton shown from the launcher click until the widget document has painted.
export const createPlaceholder = (doc: Document): HTMLElement => {
  ensurePanelStyle(doc)
  const root = doc.createElement("div")
  root.setAttribute("data-supportchat-placeholder", "")
  root.setAttribute("role", "status")
  root.setAttribute("aria-live", "polite")
  root.setAttribute("aria-label", "Loading chat")
  root.hidden = true
  const head = doc.createElement("div")
  head.className = "c365-head"
  const dot = doc.createElement("span")
  dot.className = "c365-dot"
  const line = doc.createElement("span")
  line.className = "c365-line"
  head.append(dot, line)
  const body = doc.createElement("div")
  body.className = "c365-body"
  const spin = doc.createElement("span")
  spin.className = "c365-spin"
  spin.setAttribute("aria-hidden", "true")
  const bar = doc.createElement("span")
  bar.className = "c365-bar"
  bar.setAttribute("aria-hidden", "true")
  body.append(spin, bar)
  root.append(head, body)
  doc.body.appendChild(root)
  return root
}

export const createPanel = (
  doc: Document,
  widgetOrigin: string,
  siteKey: string,
  publicKey: string,
  parentOrigin: string,
): HTMLIFrameElement => {
  ensurePanelStyle(doc)
  // oxlint-disable-next-line react/iframe-missing-sandbox -- sandbox unique-origin would break WS Origin
  const iframe = doc.createElement("iframe")
  iframe.title = "SupportChat"
  const widgetUrl = new URL("/widget", widgetOrigin)
  widgetUrl.searchParams.set("site_key", siteKey)
  widgetUrl.searchParams.set("public_key", publicKey)
  widgetUrl.searchParams.set("parent_origin", parentOrigin)
  const view = doc.defaultView
  if (view !== null && isSheetLayout(view)) {
    widgetUrl.searchParams.set("layout", "sheet")
  }
  iframe.src = widgetUrl.toString()
  iframe.setAttribute("data-supportchat-panel", "")
  iframe.style.cssText = [
    "position:fixed",
    "right:24px",
    "bottom:24px",
    "width:420px",
    "height:680px",
    "border:0",
    "border-radius:30px",
    "z-index:2147483646",
    "background:transparent",
    "box-shadow:0 20px 60px rgba(13,31,58,0.22)",
    "max-width:calc(100vw - 32px)",
    "max-height:calc(100vh - 32px)",
    "opacity:0",
    "transform:translateY(16px) scale(0.96)",
    "pointer-events:none",
  ].join(";")
  iframe.hidden = true
  doc.body.appendChild(iframe)
  return iframe
}

export const postToWidget = (state: PanelState, frame: HostToWidget) => {
  const iframe = state.iframe
  if (iframe === null || !iframe.isConnected) {
    return
  }
  const target = iframe.contentWindow
  if (target === null || target === undefined) {
    return
  }
  try {
    target.postMessage(frame, state.widgetOrigin)
  } catch {
    return
  }
}

export const pageContext = (win: Window, doc: Document) => {
  try {
    return {
      page_url: sanitizePageUrl(win.location.href),
      page_title: sanitizeTitle(doc.title),
      referrer: sanitizePageUrl(doc.referrer),
    }
  } catch {
    return { page_url: "", page_title: "", referrer: "" }
  }
}

export const sendBootstrap = (state: PanelState, win: Window, doc: Document) => {
  if (state.bootstrap === null) {
    return
  }
  if (state.bootstrap.type === "host.bootstrap") {
    postToWidget(state, { ...state.bootstrap, ...pageContext(win, doc) })
    return
  }
  postToWidget(state, state.bootstrap)
}

export const sendContext = (state: PanelState, win: Window, doc: Document) => {
  if (state.bootstrap === null) {
    return
  }
  postToWidget(state, { type: "host.context", ...pageContext(win, doc) })
}

export const acceptWidgetFrame = (
  state: PanelState,
  event: MessageEvent,
  handlers: {
    onMessage?: (conversationId: string, messageId: number) => void
    onSound?: (enabled: boolean) => void
    onReady: () => void
    onPainted: () => void
    onActivated: () => void
    onRebootstrap: (conversationId?: string) => void
    onClose: () => void
    onShowHistory: () => void
    onOpenConversation: (conversationId: string, replaceCurrent: boolean) => void
    onResetCurrent: () => void
    onDeleteAll: () => void
    onOpenUrl: (url: string) => void
  },
) => {
  if (event.origin !== state.widgetOrigin) {
    return
  }
  if (state.iframe === null || event.source !== state.iframe.contentWindow) {
    return
  }
  const frame = parseWidgetToHost(event.data)
  if (frame === null) {
    return
  }
  dispatchWidgetFrame(state, frame, handlers)
}

// The closed protocol switch is intentionally exhaustive and easier to audit than an action map.
// oxlint-disable-next-line complexity
const dispatchWidgetFrame = (
  state: PanelState,
  frame: NonNullable<ReturnType<typeof parseWidgetToHost>>,
  handlers: {
    onMessage?: (conversationId: string, messageId: number) => void
    onSound?: (enabled: boolean) => void
    onReady: () => void
    onPainted: () => void
    onActivated: () => void
    onRebootstrap: (conversationId?: string) => void
    onClose: () => void
    onShowHistory: () => void
    onOpenConversation: (conversationId: string, replaceCurrent: boolean) => void
    onResetCurrent: () => void
    onDeleteAll: () => void
    onOpenUrl: (url: string) => void
  },
) => {
  switch (frame.type) {
    case "widget.message":
      handlers.onMessage?.(frame.conversation_id, frame.message_id)
      return
    case "widget.sound":
      handlers.onSound?.(frame.enabled)
      return
    case "widget.ready":
      handlers.onReady()
      return
    case "widget.painted":
      handlers.onPainted()
      return
    case "widget.activated":
      handlers.onActivated()
      return
    case "widget.rebootstrap":
      handlers.onRebootstrap(frame.conversation_id)
      return
    case "widget.close":
      handlers.onClose()
      return
    case "widget.show_history":
      handlers.onShowHistory()
      return
    case "widget.open_conversation":
      handlers.onOpenConversation(frame.conversation_id, frame.replace_current)
      return
    case "widget.reset_current":
      handlers.onResetCurrent()
      return
    case "widget.delete_all":
      handlers.onDeleteAll()
      return
    case "widget.open_url":
      handlers.onOpenUrl(frame.url)
      return
    case "widget.resize":
      applyWidgetResize(state, frame)
      return
    default:
      return
  }
}

const prefersReducedMotion = (iframe: HTMLIFrameElement) =>
  iframe.ownerDocument.defaultView?.matchMedia?.("(prefers-reduced-motion: reduce)").matches ??
  false

const resetWidgetTransform = (iframe: HTMLIFrameElement) => {
  iframe.style.transform = "translateY(0) scale(1)"
}

const animateWidgetResize = (
  iframe: HTMLIFrameElement,
  currentWidth: number,
  currentHeight: number,
  targetWidth: number,
  targetHeight: number,
) => {
  iframe.style.transition = "none"
  iframe.style.transform = `translateY(0) scale(${currentWidth / targetWidth}, ${currentHeight / targetHeight})`
  iframe.getBoundingClientRect()
  const startTransition = () => {
    iframe.style.transition = ""
    resetWidgetTransform(iframe)
  }
  const widgetWindow = iframe.ownerDocument.defaultView
  if (widgetWindow?.requestAnimationFrame) {
    widgetWindow.requestAnimationFrame(startTransition)
    return
  }
  startTransition()
}

const applyWidgetResize = (state: PanelState, frame: { height: number; width?: number }) => {
  if (state.iframe === null) {
    return
  }
  const iframe = state.iframe
  const targetWidth = frame.width ?? Number.parseFloat(iframe.style.width)
  const targetHeight = frame.height
  const bounds = iframe.getBoundingClientRect()
  const currentWidth = bounds.width || Number.parseFloat(iframe.style.width)
  const currentHeight = bounds.height || Number.parseFloat(iframe.style.height)

  iframe.style.height = `${targetHeight}px`
  iframe.style.width = `${targetWidth}px`
  if (prefersReducedMotion(iframe) || currentWidth === 0 || currentHeight === 0) {
    resetWidgetTransform(iframe)
    return
  }
  animateWidgetResize(iframe, currentWidth, currentHeight, targetWidth, targetHeight)
}
