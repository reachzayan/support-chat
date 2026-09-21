import type { HostToWidget } from "../src/lib/postmessage"
import { requestBootstrap, type BootstrapAction, type BootstrapResult } from "./bootstrap"
import { acceptWidgetFrame, createPanel, sendBootstrap, sendContext } from "./iframe"
import { hideHostError, mountLauncher, showHostError } from "./launcher"
import { watchNavigation } from "./navigation"
import { originFromHref, originFromScript } from "./sanitize"
import { clearResumeToken, readResumeToken, writeResumeToken } from "./storage"

type LoaderConfig = { siteKey: string; publicKey: string }

type Runtime = {
  win: Window
  doc: Document
  widgetOrigin: string
  config: LoaderConfig
  launcher: HTMLButtonElement
  iframe: HTMLIFrameElement | null
  pendingResume: string | null
  bootstrap: HostToWidget | null
  opening: boolean
  panelPainted: boolean
  visitorActivated: boolean
  bootstrapAcked: boolean
  retryTimer: ReturnType<typeof setTimeout> | null
  hideTimer: ReturnType<typeof setTimeout> | null
}

const BOOTSTRAP_RETRY_COUNT = 5
const BOOTSTRAP_RETRY_MS = 100
const PANEL_MOTION_MS = 300

const reducedMotionDelay = (win: Window) => {
  try {
    return win.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : PANEL_MOTION_MS
  } catch {
    return 0
  }
}

const resumeFor = (runtime: Runtime) => {
  return runtime.pendingResume ?? readResumeToken(runtime.config.siteKey)
}

const clearRetryTimer = (runtime: Runtime) => {
  if (runtime.retryTimer !== null) {
    clearTimeout(runtime.retryTimer)
    runtime.retryTimer = null
  }
}

const clearHideTimer = (runtime: Runtime) => {
  if (runtime.hideTimer !== null) {
    clearTimeout(runtime.hideTimer)
    runtime.hideTimer = null
  }
}

const setLauncherBusy = (runtime: Runtime, busy: boolean) => {
  runtime.launcher.setAttribute("aria-busy", busy ? "true" : "false")
}

const bootstrapFrame = (runtime: Runtime) => {
  return runtime.bootstrap
}

const panelState = (runtime: Runtime) => {
  return {
    widgetOrigin: runtime.widgetOrigin,
    iframe: runtime.iframe,
    pendingResume: runtime.pendingResume,
    bootstrap: bootstrapFrame(runtime),
    launcher: runtime.launcher,
  }
}

const sendCurrentBootstrap = (runtime: Runtime) => {
  if (runtime.iframe === null || !runtime.iframe.isConnected) {
    return
  }
  sendBootstrap(panelState(runtime), runtime.win, runtime.doc)
}

const sendBootstrapWithRetry = (runtime: Runtime) => {
  clearRetryTimer(runtime)
  let attempt = 0
  const tick = () => {
    runtime.retryTimer = null
    if (
      runtime.bootstrapAcked ||
      runtime.bootstrap === null ||
      runtime.iframe === null ||
      !runtime.iframe.isConnected
    ) {
      return
    }
    sendCurrentBootstrap(runtime)
    attempt += 1
    if (attempt < BOOTSTRAP_RETRY_COUNT) {
      runtime.retryTimer = setTimeout(tick, BOOTSTRAP_RETRY_MS)
    }
  }
  tick()
}

const hidePanel = (runtime: Runtime) => {
  clearHideTimer(runtime)
  setLauncherBusy(runtime, false)
  if (runtime.iframe !== null) {
    runtime.iframe.style.opacity = "0"
    runtime.iframe.style.transform = "translateY(16px) scale(0.96)"
    runtime.iframe.style.pointerEvents = "none"
    const delay = reducedMotionDelay(runtime.win)
    runtime.hideTimer = setTimeout(() => {
      runtime.hideTimer = null
      if (runtime.iframe !== null && runtime.launcher.hidden === false) {
        runtime.iframe.hidden = true
      }
    }, delay)
  }
  runtime.launcher.hidden = false
  runtime.launcher.focus()
}

const showPanel = (runtime: Runtime) => {
  clearHideTimer(runtime)
  setLauncherBusy(runtime, false)
  if (runtime.iframe !== null) {
    runtime.iframe.hidden = false
    runtime.iframe.style.pointerEvents = "auto"
    runtime.win.requestAnimationFrame(() => {
      if (runtime.iframe === null) {
        return
      }
      runtime.iframe.style.opacity = "1"
      runtime.iframe.style.transform = "translateY(0) scale(1)"
    })
  }
  runtime.launcher.hidden = true
}

const persistResumeIfReady = (runtime: Runtime) => {
  if (!runtime.visitorActivated || runtime.pendingResume === null) {
    return
  }
  writeResumeToken(runtime.config.siteKey, runtime.pendingResume)
}

const persistActivated = (runtime: Runtime) => {
  runtime.visitorActivated = true
  runtime.bootstrapAcked = true
  clearRetryTimer(runtime)
  persistResumeIfReady(runtime)
}

const warmPanel = (runtime: Runtime) => {
  if (runtime.iframe !== null) {
    return
  }
  runtime.iframe = createPanel(
    runtime.doc,
    runtime.widgetOrigin,
    runtime.config.siteKey,
    runtime.config.publicKey,
    originFromHref(runtime.win.location.href),
  )
}

const applyBootstrap = (
  runtime: Runtime,
  result: Exclude<BootstrapResult, { mode: "forgotten" }>,
) => {
  if (result.mode === "conversation") {
    runtime.bootstrap = {
      type: "host.bootstrap",
      bootstrap_token: result.bootstrap_token,
      widget: result.widget,
      page_url: "",
      page_title: "",
      referrer: "",
      ...(result.conversation === undefined ? {} : { conversation: result.conversation }),
    }
  } else if (result.mode === "identity") {
    runtime.bootstrap = { type: "host.identity", widget: result.widget, identity: result.identity }
  } else {
    runtime.bootstrap = {
      type: "host.history",
      widget: result.widget,
      identity: result.identity,
      conversations: result.conversations,
    }
  }
  runtime.bootstrapAcked = false
  if (result.mode === "conversation" && result.resume_token !== undefined) {
    runtime.pendingResume = result.resume_token
  }
  warmPanel(runtime)
  hideHostError(runtime.doc)
  persistResumeIfReady(runtime)
}

const handleHostMessage = (runtime: Runtime, event: MessageEvent) => {
  acceptWidgetFrame(panelState(runtime), event, {
    onReady: () => sendBootstrapWithRetry(runtime),
    onPainted: () => {
      runtime.panelPainted = true
      showPanel(runtime)
    },
    onActivated: () => persistActivated(runtime),
    onRebootstrap: (conversationId) => {
      void runBootstrap(runtime, {
        action: conversationId ? "refresh" : "identify",
        conversationId,
      })
    },
    onClose: () => hidePanel(runtime),
    onShowHistory: () => void runBootstrap(runtime, { action: "history" }),
    onOpenConversation: (conversationId, replaceCurrent) =>
      void runBootstrap(runtime, {
        action: "open",
        conversationId,
        replaceCurrent,
      }),
    onResetCurrent: () => void runBootstrap(runtime, { action: "reset" }),
    onDeleteAll: () => void runBootstrap(runtime, { action: "forget" }),
    onOpenUrl: (url) => {
      runtime.win.open(url, "_blank", "noopener,noreferrer")
    },
  })
}

const runBootstrap = async (runtime: Runtime, options: BootstrapAction = {}) => {
  if (runtime.opening) {
    return
  }
  runtime.opening = true
  const result = await requestBootstrap(
    runtime.widgetOrigin,
    runtime.config.siteKey,
    runtime.config.publicKey,
    resumeFor(runtime),
    options,
  )
  runtime.opening = false
  if (result === null) {
    setLauncherBusy(runtime, false)
    showHostError(runtime.doc, () => {
      void runBootstrap(runtime)
    })
    return
  }
  if (result.mode === "forgotten") {
    clearResumeToken(runtime.config.siteKey)
    runtime.pendingResume = null
    runtime.bootstrap = null
    runtime.visitorActivated = false
    void runBootstrap(runtime)
    return
  }
  applyBootstrap(runtime, result)
  sendBootstrapWithRetry(runtime)
}

const handleOpen = (runtime: Runtime) => {
  hideHostError(runtime.doc)
  if (runtime.iframe !== null && runtime.panelPainted) {
    showPanel(runtime)
    return
  }
  setLauncherBusy(runtime, true)
  warmPanel(runtime)
  void runBootstrap(runtime)
}

const preconnectWidget = (doc: Document, widgetOrigin: string) => {
  if (doc.querySelector(`link[rel="preconnect"][href="${widgetOrigin}"]`) !== null) {
    return
  }
  const link = doc.createElement("link")
  link.rel = "preconnect"
  link.setAttribute("href", widgetOrigin)
  doc.head.appendChild(link)
}

export const installSupportChat = (win: Window, doc: Document, script: HTMLScriptElement | null) => {
  if (win.__supportchatInstalled === true) {
    return
  }
  const widgetOrigin = originFromScript(script)
  const config = win.__supportchat
  if (
    widgetOrigin === "" ||
    config === undefined ||
    config.siteKey === "" ||
    config.publicKey === ""
  ) {
    console.error("SupportChat: widget configuration is missing")
    return
  }
  win.__supportchatInstalled = true
  preconnectWidget(doc, widgetOrigin)
  const runtime: Runtime = {
    win,
    doc,
    widgetOrigin,
    config: { siteKey: config.siteKey, publicKey: config.publicKey },
    launcher: doc.createElement("button"),
    iframe: null,
    pendingResume: null,
    bootstrap: null,
    opening: false,
    panelPainted: false,
    visitorActivated: false,
    bootstrapAcked: false,
    retryTimer: null,
    hideTimer: null,
  }
  runtime.launcher = mountLauncher(doc, () => handleOpen(runtime))
  runtime.launcher.addEventListener("pointerenter", () => warmPanel(runtime))
  runtime.launcher.addEventListener("focus", () => warmPanel(runtime))
  win.addEventListener("message", (event: MessageEvent) => handleHostMessage(runtime, event))
  watchNavigation(win, () => {
    sendContext(panelState(runtime), win, doc)
  })
}
