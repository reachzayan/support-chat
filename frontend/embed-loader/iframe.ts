import { parseWidgetToHost, type HostToWidget } from "../src/lib/postmessage"
import { sanitizePageUrl, sanitizeTitle } from "./sanitize"

type PanelState = {
  widgetOrigin: string
  iframe: HTMLIFrameElement | null
  pendingResume: string | null
  bootstrap: HostToWidget | null
  launcher: HTMLButtonElement
}

const PANEL_STYLE = [
  "[data-supportchat-panel]{transform-origin:bottom right;transition:opacity 220ms ease,transform 300ms cubic-bezier(0.22,1,0.36,1),border-radius 300ms cubic-bezier(0.22,1,0.36,1);will-change:transform,opacity}",
  "@media (prefers-reduced-motion: reduce){[data-supportchat-panel]{transition:none}}",
].join("")

const ensurePanelStyle = (doc: Document) => {
  if (doc.querySelector("[data-supportchat-panel-style]") !== null) {
    return
  }
  const style = doc.createElement("style")
  style.setAttribute("data-supportchat-panel-style", "")
  style.textContent = PANEL_STYLE
  doc.head.appendChild(style)
}

export const createPanel = (doc: Document, widgetOrigin: string): HTMLIFrameElement => {
  ensurePanelStyle(doc)
  // oxlint-disable-next-line react/iframe-missing-sandbox -- sandbox unique-origin would break WS Origin
  const iframe = doc.createElement("iframe")
  iframe.title = "SupportChat"
  iframe.src = `${widgetOrigin}/widget`
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
  ].join(";")
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
  if (state.bootstrap === null || state.bootstrap.type !== "host.bootstrap") {
    return
  }
  postToWidget(state, { ...state.bootstrap, ...pageContext(win, doc) })
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
    onReady: () => void
    onActivated: () => void
    onRebootstrap: () => void
    onClose: () => void
    onReset: () => void
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

const dispatchWidgetFrame = (
  state: PanelState,
  frame: NonNullable<ReturnType<typeof parseWidgetToHost>>,
  handlers: {
    onReady: () => void
    onActivated: () => void
    onRebootstrap: () => void
    onClose: () => void
    onReset: () => void
    onOpenUrl: (url: string) => void
  },
) => {
  switch (frame.type) {
    case "widget.ready":
      handlers.onReady()
      return
    case "widget.activated":
      handlers.onActivated()
      return
    case "widget.rebootstrap":
      handlers.onRebootstrap()
      return
    case "widget.close":
      handlers.onClose()
      return
    case "widget.reset":
      handlers.onReset()
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
