"use strict"
;(() => {
  // embed-loader/bootstrap.ts
  var isRecord = (value) => {
    return typeof value === "object" && value !== null
  }
  var parseWidget = (value) => {
    if (!isRecord(value)) {
      return null
    }
    if (
      typeof value.name !== "string" ||
      typeof value.greeting !== "string" ||
      typeof value.privacy_url !== "string"
    ) {
      return null
    }
    return {
      name: value.name,
      greeting: value.greeting,
      privacy_url: value.privacy_url,
      bot_enabled: value.bot_enabled !== false,
      human_enabled: value.human_enabled !== false,
    }
  }
  var parseBootstrapResult = (value) => {
    if (!isRecord(value) || typeof value.bootstrap_token !== "string") {
      return null
    }
    const widget = parseWidget(value.widget)
    if (widget === null) {
      return null
    }
    const resume =
      typeof value.resume_token === "string" ? { resume_token: value.resume_token } : {}
    return { widget, bootstrap_token: value.bootstrap_token, ...resume }
  }
  var requestBootstrap = async (widgetOrigin, siteKey, publicKey, resumeToken) => {
    const body = {
      site_key: siteKey,
      public_key: publicKey,
      resume_token: resumeToken,
    }
    try {
      const response = await fetch(`${widgetOrigin}/api/public/widget-bootstrap`, {
        method: "POST",
        headers: { "Content-Type": "text/plain;charset=UTF-8" },
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        return null
      }
      return parseBootstrapResult(await response.json())
    } catch (e) {
      return null
    }
  }

  // src/lib/postmessage.ts
  var WIDGET_RESIZE_MIN = 320
  var WIDGET_RESIZE_MAX = 720
  var WIDGET_WIDTH_MIN = 360
  var WIDGET_WIDTH_MAX = 560
  var isRecord2 = (value) => {
    return typeof value === "object" && value !== null
  }
  var parseResize = (value) => {
    if (typeof value.height !== "number" || !Number.isInteger(value.height)) {
      return null
    }
    if (value.height < WIDGET_RESIZE_MIN || value.height > WIDGET_RESIZE_MAX) {
      return null
    }
    if (value.width === void 0) {
      return { type: "widget.resize", height: value.height }
    }
    if (typeof value.width !== "number" || !Number.isInteger(value.width)) {
      return null
    }
    if (value.width < WIDGET_WIDTH_MIN || value.width > WIDGET_WIDTH_MAX) {
      return null
    }
    return { type: "widget.resize", height: value.height, width: value.width }
  }
  var parseWidgetToHost = (value) => {
    if (!isRecord2(value) || typeof value.type !== "string") {
      return null
    }
    if (
      value.type === "widget.ready" ||
      value.type === "widget.rebootstrap" ||
      value.type === "widget.activated" ||
      value.type === "widget.close" ||
      value.type === "widget.reset"
    ) {
      return { type: value.type }
    }
    if (value.type === "widget.resize") {
      return parseResize(value)
    }
    if (value.type === "widget.open_url") {
      if (typeof value.url !== "string") {
        return null
      }
      try {
        const parsed = new URL(value.url)
        if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
          return null
        }
      } catch (e) {
        return null
      }
      return { type: "widget.open_url", url: value.url }
    }
    return null
  }

  // embed-loader/sanitize.ts
  var MAX_URL = 2048
  var MAX_TITLE = 200
  var originFromHref = (href) => {
    try {
      const url = new URL(href)
      if (url.protocol !== "http:" && url.protocol !== "https:") {
        return ""
      }
      return url.origin
    } catch (e) {
      return ""
    }
  }
  var sanitizePageUrl = (raw) => {
    const clipped = raw.length > MAX_URL ? raw.slice(0, MAX_URL) : raw
    try {
      const url = new URL(clipped)
      if (url.protocol !== "http:" && url.protocol !== "https:") {
        return ""
      }
      return `${url.origin}${url.pathname}`
    } catch (e) {
      return ""
    }
  }
  var sanitizeTitle = (raw) => raw.slice(0, MAX_TITLE)
  var originFromScript = (script2) => {
    if (script2 === null || script2.src === "") {
      return ""
    }
    return originFromHref(script2.src)
  }

  // embed-loader/iframe.ts
  var PANEL_STYLE = [
    "[data-supportchat-panel]{transform-origin:bottom right;transition:width 220ms cubic-bezier(0.22,1,0.36,1),height 220ms cubic-bezier(0.22,1,0.36,1),opacity 200ms ease,transform 220ms cubic-bezier(0.22,1,0.36,1)}",
    "@media (prefers-reduced-motion: reduce){[data-supportchat-panel]{transition:none}}",
  ].join("")
  var ensurePanelStyle = (doc) => {
    if (doc.querySelector("[data-supportchat-panel-style]") !== null) {
      return
    }
    const style = doc.createElement("style")
    style.setAttribute("data-supportchat-panel-style", "")
    style.textContent = PANEL_STYLE
    doc.head.appendChild(style)
  }
  var createPanel = (doc, widgetOrigin) => {
    ensurePanelStyle(doc)
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
      "border-radius:18px",
      "z-index:2147483646",
      "background:#FFFFFF",
      "box-shadow:0 16px 40px rgba(11,35,71,0.28)",
      "max-width:calc(100vw - 32px)",
      "max-height:calc(100vh - 32px)",
      "opacity:1",
      "transform:translateY(0) scale(1)",
    ].join(";")
    doc.body.appendChild(iframe)
    return iframe
  }
  var postToWidget = (state, frame) => {
    const iframe = state.iframe
    if (iframe === null || !iframe.isConnected) {
      return
    }
    const target = iframe.contentWindow
    if (target === null || target === void 0) {
      return
    }
    try {
      target.postMessage(frame, state.widgetOrigin)
    } catch (e) {
      return
    }
  }
  var pageContext = (win, doc) => {
    try {
      return {
        page_url: sanitizePageUrl(win.location.href),
        page_title: sanitizeTitle(doc.title),
        referrer: sanitizePageUrl(doc.referrer),
      }
    } catch (e) {
      return { page_url: "", page_title: "", referrer: "" }
    }
  }
  var sendBootstrap = (state, win, doc) => {
    if (state.bootstrap === null || state.bootstrap.type !== "host.bootstrap") {
      return
    }
    postToWidget(state, { ...state.bootstrap, ...pageContext(win, doc) })
  }
  var sendContext = (state, win, doc) => {
    if (state.bootstrap === null) {
      return
    }
    postToWidget(state, { type: "host.context", ...pageContext(win, doc) })
  }
  var acceptWidgetFrame = (state, event, handlers) => {
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
    if (frame.type === "widget.ready") {
      handlers.onReady()
      return
    }
    if (frame.type === "widget.activated") {
      handlers.onActivated()
      return
    }
    if (frame.type === "widget.rebootstrap") {
      handlers.onRebootstrap()
      return
    }
    if (frame.type === "widget.close") {
      handlers.onClose()
      return
    }
    if (frame.type === "widget.reset") {
      handlers.onReset()
      return
    }
    if (frame.type === "widget.open_url") {
      handlers.onOpenUrl(frame.url)
      return
    }
    if (state.iframe !== null) {
      state.iframe.style.height = `${frame.height}px`
      if (frame.width !== void 0) {
        state.iframe.style.width = `${frame.width}px`
      }
    }
  }

  // embed-loader/launcher.ts
  var NAVY = "#0B2347"
  var STEEL = "#2456A0"
  var PAPER = "#FFFFFF"
  var INK = "#0D1F3A"
  var mountLauncher = (doc, handleOpen2) => {
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
    button.addEventListener("click", handleOpen2)
    doc.body.appendChild(button)
    return button
  }
  var showHostError = (doc, handleRetry) => {
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
  var hideHostError = (doc) => {
    const existing = doc.querySelector("[data-supportchat-error]")
    if (existing instanceof HTMLElement) {
      existing.hidden = true
    }
  }

  // embed-loader/navigation.ts
  var NAVIGATE_MS = 300
  var watchNavigation = (win, notify) => {
    let timer = 0
    const debounced = () => {
      win.clearTimeout(timer)
      timer = win.setTimeout(notify, NAVIGATE_MS)
    }
    const history = win.history
    const push = history.pushState.bind(history)
    const replace = history.replaceState.bind(history)
    history.pushState = (data, unused, url) => {
      const result = push(data, unused, url)
      debounced()
      return result
    }
    history.replaceState = (data, unused, url) => {
      const result = replace(data, unused, url)
      debounced()
      return result
    }
    win.addEventListener("popstate", debounced)
    const navigation = win.navigation
    if (navigation !== void 0) {
      navigation.addEventListener("navigate", debounced)
    }
  }

  // embed-loader/storage.ts
  var visitorStorageKey = (siteKey) => `supportchat.visitor.${siteKey}`
  var readResumeToken = (siteKey) => {
    try {
      return window.localStorage.getItem(visitorStorageKey(siteKey))
    } catch (e) {
      return null
    }
  }
  var writeResumeToken = (siteKey, token) => {
    try {
      window.localStorage.setItem(visitorStorageKey(siteKey), token)
    } catch (e) {
      return
    }
  }
  var clearResumeToken = (siteKey) => {
    try {
      window.localStorage.removeItem(visitorStorageKey(siteKey))
    } catch (e) {
      return
    }
  }

  // embed-loader/install.ts
  var BOOTSTRAP_RETRY_COUNT = 5
  var BOOTSTRAP_RETRY_MS = 100
  var reducedMotionDelay = (win) => {
    try {
      return win.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 200
    } catch (e) {
      return 0
    }
  }
  var resumeFor = (runtime) => {
    var _a
    return (_a = readResumeToken(runtime.config.siteKey)) != null ? _a : runtime.pendingResume
  }
  var clearRetryTimer = (runtime) => {
    if (runtime.retryTimer !== null) {
      clearTimeout(runtime.retryTimer)
      runtime.retryTimer = null
    }
  }
  var clearHideTimer = (runtime) => {
    if (runtime.hideTimer !== null) {
      clearTimeout(runtime.hideTimer)
      runtime.hideTimer = null
    }
  }
  var bootstrapFrame = (runtime) => {
    if (runtime.bootstrapToken === null || runtime.widget === null) {
      return null
    }
    return {
      type: "host.bootstrap",
      bootstrap_token: runtime.bootstrapToken,
      widget: runtime.widget,
      page_url: "",
      page_title: "",
      referrer: "",
    }
  }
  var panelState = (runtime) => {
    return {
      widgetOrigin: runtime.widgetOrigin,
      iframe: runtime.iframe,
      pendingResume: runtime.pendingResume,
      bootstrap: bootstrapFrame(runtime),
      launcher: runtime.launcher,
    }
  }
  var sendCurrentBootstrap = (runtime) => {
    if (runtime.iframe === null || !runtime.iframe.isConnected) {
      return
    }
    sendBootstrap(panelState(runtime), runtime.win, runtime.doc)
  }
  var sendBootstrapWithRetry = (runtime) => {
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
  var hidePanel = (runtime) => {
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
  var showPanel = (runtime) => {
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
  var resetPanel = (runtime) => {
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
  var persistActivated = (runtime) => {
    runtime.bootstrapAcked = true
    clearRetryTimer(runtime)
    if (runtime.pendingResume !== null) {
      writeResumeToken(runtime.config.siteKey, runtime.pendingResume)
    }
  }
  var applyBootstrap = (runtime, token, widget, resume) => {
    runtime.bootstrapToken = token
    runtime.widget = widget
    runtime.bootstrapAcked = false
    if (resume !== void 0) {
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
  var handleHostMessage = (runtime, event) => {
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
  var runBootstrap = async (runtime) => {
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
  var handleOpen = (runtime) => {
    hideHostError(runtime.doc)
    if (runtime.iframe !== null) {
      showPanel(runtime)
      return
    }
    void runBootstrap(runtime)
  }
  var installSupportChat = (win, doc, script2) => {
    const widgetOrigin = originFromScript(script2)
    const config = win.__supportchat
    if (
      widgetOrigin === "" ||
      config === void 0 ||
      config.siteKey === "" ||
      config.publicKey === ""
    ) {
      console.error("SupportChat: widget configuration is missing")
      return
    }
    const runtime = {
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
    win.addEventListener("message", (event) => handleHostMessage(runtime, event))
    watchNavigation(win, () => {
      sendContext(panelState(runtime), win, doc)
    })
  }

  // embed-loader/index.ts
  var script = document.currentScript
  installSupportChat(window, document, script instanceof HTMLScriptElement ? script : null)
})()
