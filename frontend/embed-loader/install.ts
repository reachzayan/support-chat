import { requestBootstrap, type PublicWidgetConfig } from "./bootstrap"
import { acceptWidgetFrame, createPanel, sendBootstrap, sendContext } from "./iframe"
import { hideHostError, mountLauncher, showHostError } from "./launcher"
import { watchNavigation } from "./navigation"
import { originFromScript } from "./sanitize"
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
  bootstrapToken: string | null
  widget: PublicWidgetConfig | null
  opening: boolean
  bootstrapAcked: boolean
  retryTimer: ReturnType<typeof setTimeout> | null
  hideTimer: ReturnType<typeof setTimeout> | null
}

const BOOTSTRAP_RETRY_COUNT = 5
const BOOTSTRAP_RETRY_MS = 100

const reducedMotionDelay = (win: Window) => {
  try {
    return win.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 200
  } catch {
    return 0
  }
}

const resumeFor = (runtime: Runtime) => {
  return readResumeToken(runtime.config.siteKey) ?? runtime.pendingResume
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

const bootstrapFrame = (runtime: Runtime) => {
  if (runtime.bootstrapToken === null || runtime.widget === null) {
    return null
  }
  return {
    type: "host.bootstrap" as const,
    bootstrap_token: runtime.bootstrapToken,
    widget: runtime.widget,
    page_url: "",
    page_title: "",
    referrer: "",
  }
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
      runtime.bootstrapToken === null ||
      runtime.widget === null ||
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
  if (runtime.iframe !== null) {
    runtime.iframe.style.opacity = "0"
    runtime.iframe.style.transform = "translateY(16px) scale(0.96)"
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
  if (runtime.iframe !== null) {
    runtime.iframe.hidden = false
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

const resetPanel = (runtime: Runtime) => {
  clearRetryTimer(runtime)
  clearHideTimer(runtime)
  clearResumeToken(runtime.config.siteKey)
  runtime.pendingResume = null
  runtime.bootstrapToken = null
  runtime.widget = null
  runtime.bootstrapAcked = false
  if (runtime.iframe !== null) {
    runtime.iframe.remove()
    runtime.iframe = null
  }
  runtime.launcher.hidden = false
  runtime.launcher.focus()
}

const persistActivated = (runtime: Runtime) => {
  runtime.bootstrapAcked = true
  clearRetryTimer(runtime)
  if (runtime.pendingResume !== null) {
    writeResumeToken(runtime.config.siteKey, runtime.pendingResume)
  }
}

const applyBootstrap = (
  runtime: Runtime,
  token: string,
  widget: PublicWidgetConfig,
  resume?: string,
) => {
  runtime.bootstrapToken = token
  runtime.widget = widget
  runtime.bootstrapAcked = false
  if (resume !== undefined) {
    runtime.pendingResume = resume
  }
  if (runtime.iframe === null) {
    runtime.iframe = createPanel(runtime.doc, runtime.widgetOrigin)
  }
  runtime.iframe.hidden = false
  runtime.iframe.style.opacity = "1"
  runtime.iframe.style.transform = "translateY(0) scale(1)"
  runtime.launcher.hidden = true
  hideHostError(runtime.doc)
}

const handleHostMessage = (runtime: Runtime, event: MessageEvent) => {
  acceptWidgetFrame(panelState(runtime), event, {
    onReady: () => sendBootstrapWithRetry(runtime),
    onActivated: () => persistActivated(runtime),
    onRebootstrap: () => {
      void runBootstrap(runtime)
    },
    onClose: () => hidePanel(runtime),
    onReset: () => resetPanel(runtime),
    onOpenUrl: (url) => {
      runtime.win.open(url, "_blank", "noopener,noreferrer")
    },
  })
}

const runBootstrap = async (runtime: Runtime) => {
  if (runtime.opening) {
    return
  }
  runtime.opening = true
  const result = await requestBootstrap(
    runtime.widgetOrigin,
    runtime.config.siteKey,
    runtime.config.publicKey,
    resumeFor(runtime),
  )
  runtime.opening = false
  if (result === null) {
    showHostError(runtime.doc, () => {
      void runBootstrap(runtime)
    })
    return
  }
  applyBootstrap(runtime, result.bootstrap_token, result.widget, result.resume_token)
  sendBootstrapWithRetry(runtime)
}

const handleOpen = (runtime: Runtime) => {
  hideHostError(runtime.doc)
  if (runtime.iframe !== null) {
    showPanel(runtime)
    return
  }
  void runBootstrap(runtime)
}

export const installSupportChat = (win: Window, doc: Document, script: HTMLScriptElement | null) => {
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
  const runtime: Runtime = {
    win,
    doc,
    widgetOrigin,
    config: { siteKey: config.siteKey, publicKey: config.publicKey },
    launcher: doc.createElement("button"),
    iframe: null,
    pendingResume: null,
    bootstrapToken: null,
    widget: null,
    opening: false,
    bootstrapAcked: false,
    retryTimer: null,
    hideTimer: null,
  }
  runtime.launcher = mountLauncher(doc, () => handleOpen(runtime))
  win.addEventListener("message", (event: MessageEvent) => handleHostMessage(runtime, event))
  watchNavigation(win, () => {
    sendContext(panelState(runtime), win, doc)
  })
}
