"use strict";
(() => {
  // src/lib/postmessage.ts
  var WIDGET_RESIZE_MIN = 320;
  var WIDGET_RESIZE_MAX = 720;
  var WIDGET_WIDTH_MIN = 360;
  var WIDGET_WIDTH_MAX = 560;
  var isRecord = (value) => {
    return typeof value === "object" && value !== null;
  };
  var parseWidgetConfig = (value) => {
    if (!isRecord(value)) {
      return null;
    }
    if (typeof value.name !== "string" || typeof value.greeting !== "string" || typeof value.privacy_url !== "string") {
      return null;
    }
    const contactInfo = Array.isArray(value.contact_info) ? value.contact_info.filter(
      (item) => typeof item === "string" && item.trim() !== ""
    ) : [];
    return {
      name: value.name,
      greeting: value.greeting,
      privacy_url: value.privacy_url,
      contact_info: contactInfo,
      bot_enabled: value.bot_enabled !== false,
      human_enabled: value.human_enabled !== false
    };
  };
  var SNAPSHOT_STATES = /* @__PURE__ */ new Set(["prechat", "bot", "queued", "human", "closed"]);
  var UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  var parseAssignedAgent = (value) => {
    if (value === null) {
      return null;
    }
    if (!isRecord(value) || typeof value.id !== "string" || typeof value.display_name !== "string") {
      return void 0;
    }
    return { id: value.id, display_name: value.display_name };
  };
  var parseConversationSnapshot = (value) => {
    if (!isRecord(value) || typeof value.state !== "string" || !SNAPSHOT_STATES.has(value.state)) {
      return void 0;
    }
    if (!Array.isArray(value.messages)) {
      return void 0;
    }
    const assigned = value.assigned_agent === void 0 ? null : parseAssignedAgent(value.assigned_agent);
    if (assigned === void 0) {
      return void 0;
    }
    return {
      ...typeof value.id === "string" && UUID_PATTERN.test(value.id) ? { id: value.id } : {},
      state: value.state,
      assigned_agent: assigned,
      messages: value.messages.filter(isRecord)
    };
  };
  var parseIdentity = (value) => {
    if (!isRecord(value) || typeof value.display_name !== "string" || typeof value.email_hint !== "string" || value.phone_hint !== null && typeof value.phone_hint !== "string" || typeof value.chat_count !== "number" || !Number.isInteger(value.chat_count) || value.chat_count < 0) {
      return null;
    }
    return {
      display_name: value.display_name,
      email_hint: value.email_hint,
      phone_hint: value.phone_hint,
      chat_count: value.chat_count
    };
  };
  var parseHistoryItem = (value) => {
    if (!isRecord(value) || typeof value.id !== "string" || !UUID_PATTERN.test(value.id) || typeof value.state !== "string" || !SNAPSHOT_STATES.has(value.state) || value.inquiry_type !== null && typeof value.inquiry_type !== "string" || typeof value.created_at !== "string" || !Number.isFinite(Date.parse(value.created_at)) || typeof value.last_message_at !== "string" || !Number.isFinite(Date.parse(value.last_message_at)) || typeof value.is_current !== "boolean") {
      return null;
    }
    const assigned = parseAssignedAgent(value.assigned_agent);
    if (assigned === void 0) {
      return null;
    }
    return {
      id: value.id,
      state: value.state,
      inquiry_type: value.inquiry_type,
      created_at: value.created_at,
      last_message_at: value.last_message_at,
      assigned_agent: assigned,
      is_current: value.is_current
    };
  };
  var parseReturningFrame = (value) => {
    const widget = parseWidgetConfig(value.widget);
    const identity = parseIdentity(value.identity);
    if (widget === null || identity === null) {
      return null;
    }
    if (value.type === "host.identity") {
      return { type: "host.identity", widget, identity };
    }
    if (value.type !== "host.history" || !Array.isArray(value.conversations)) {
      return null;
    }
    const conversations = value.conversations.map(parseHistoryItem);
    if (conversations.some((item) => item === null)) {
      return null;
    }
    return {
      type: "host.history",
      widget,
      identity,
      conversations
    };
  };
  var parseBootstrap = (value) => {
    const widget = parseWidgetConfig(value.widget);
    if (typeof value.bootstrap_token !== "string" || widget === null) {
      return null;
    }
    if (typeof value.page_url !== "string" || typeof value.page_title !== "string" || typeof value.referrer !== "string") {
      return null;
    }
    const conversation = parseConversationSnapshot(value.conversation);
    return {
      type: "host.bootstrap",
      bootstrap_token: value.bootstrap_token,
      widget,
      page_url: value.page_url,
      page_title: value.page_title,
      referrer: value.referrer,
      ...conversation === void 0 ? {} : { conversation }
    };
  };
  var parseContext = (value) => {
    if (typeof value.page_url !== "string" || typeof value.page_title !== "string" || typeof value.referrer !== "string") {
      return null;
    }
    return {
      type: "host.context",
      page_url: value.page_url,
      page_title: value.page_title,
      referrer: value.referrer
    };
  };
  var parseHostToWidget = (value) => {
    if (!isRecord(value) || typeof value.type !== "string") {
      return null;
    }
    if (value.type === "host.bootstrap") {
      return parseBootstrap(value);
    }
    if (value.type === "host.identity" || value.type === "host.history") {
      return parseReturningFrame(value);
    }
    if (value.type === "host.context") {
      return parseContext(value);
    }
    return null;
  };
  var parseResize = (value) => {
    if (typeof value.height !== "number" || !Number.isInteger(value.height)) {
      return null;
    }
    if (value.height < WIDGET_RESIZE_MIN || value.height > WIDGET_RESIZE_MAX) {
      return null;
    }
    if (value.width === void 0) {
      return { type: "widget.resize", height: value.height };
    }
    if (typeof value.width !== "number" || !Number.isInteger(value.width)) {
      return null;
    }
    if (value.width < WIDGET_WIDTH_MIN || value.width > WIDGET_WIDTH_MAX) {
      return null;
    }
    return { type: "widget.resize", height: value.height, width: value.width };
  };
  var SIMPLE_WIDGET_TYPES = /* @__PURE__ */ new Set([
    "widget.ready",
    "widget.painted",
    "widget.activated",
    "widget.close",
    "widget.show_history",
    "widget.reset_current",
    "widget.delete_all"
  ]);
  var parseSimpleWidget = (type) => {
    if (!SIMPLE_WIDGET_TYPES.has(type)) {
      return null;
    }
    return { type };
  };
  var parseOpenUrl = (value) => {
    if (typeof value.url !== "string") {
      return null;
    }
    try {
      const parsed = new URL(value.url);
      if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
        return null;
      }
    } catch (e) {
      return null;
    }
    return { type: "widget.open_url", url: value.url };
  };
  var parseWidgetToHost = (value) => {
    if (!isRecord(value) || typeof value.type !== "string") {
      return null;
    }
    const simple = parseSimpleWidget(value.type);
    if (simple !== null) {
      return simple;
    }
    if (value.type === "widget.resize") {
      return parseResize(value);
    }
    if (value.type === "widget.rebootstrap") {
      if (value.conversation_id === void 0) {
        return { type: "widget.rebootstrap" };
      }
      if (typeof value.conversation_id !== "string" || !UUID_PATTERN.test(value.conversation_id)) {
        return null;
      }
      return { type: "widget.rebootstrap", conversation_id: value.conversation_id };
    }
    if (value.type === "widget.open_conversation") {
      if (typeof value.conversation_id !== "string" || !UUID_PATTERN.test(value.conversation_id) || typeof value.replace_current !== "boolean") {
        return null;
      }
      return {
        type: "widget.open_conversation",
        conversation_id: value.conversation_id,
        replace_current: value.replace_current
      };
    }
    if (value.type === "widget.open_url") {
      return parseOpenUrl(value);
    }
    return null;
  };

  // embed-loader/bootstrap.ts
  var isRecord2 = (value) => {
    return typeof value === "object" && value !== null;
  };
  var parseWidget = (value) => {
    if (!isRecord2(value)) {
      return null;
    }
    if (typeof value.name !== "string" || typeof value.greeting !== "string" || typeof value.privacy_url !== "string") {
      return null;
    }
    const contactInfo = Array.isArray(value.contact_info) ? value.contact_info.filter(
      (item) => typeof item === "string" && item.trim() !== ""
    ) : [];
    return {
      name: value.name,
      greeting: value.greeting,
      privacy_url: value.privacy_url,
      contact_info: contactInfo,
      bot_enabled: value.bot_enabled !== false,
      human_enabled: value.human_enabled !== false
    };
  };
  var parseBootstrapResult = (value) => {
    if (!isRecord2(value)) {
      return null;
    }
    const widget = parseWidget(value.widget);
    if (widget === null) {
      return null;
    }
    if (value.mode === "identity" || value.mode === "history") {
      const frame = parseHostToWidget({
        type: value.mode === "identity" ? "host.identity" : "host.history",
        widget: value.widget,
        identity: value.identity,
        ...value.mode === "history" ? { conversations: value.conversations } : {}
      });
      if ((frame == null ? void 0 : frame.type) === "host.identity") {
        return { mode: "identity", widget, identity: frame.identity };
      }
      if ((frame == null ? void 0 : frame.type) === "host.history") {
        return {
          mode: "history",
          widget,
          identity: frame.identity,
          conversations: frame.conversations
        };
      }
      return null;
    }
    if (value.mode === "forgotten") {
      return { mode: "forgotten", widget };
    }
    if (typeof value.bootstrap_token !== "string") {
      return null;
    }
    const resume = typeof value.resume_token === "string" ? { resume_token: value.resume_token } : {};
    const conversation = parseConversationSnapshot(value.conversation);
    return {
      mode: "conversation",
      widget,
      bootstrap_token: value.bootstrap_token,
      ...resume,
      ...conversation === void 0 ? {} : { conversation }
    };
  };
  var requestBootstrap = async (widgetOrigin, siteKey, publicKey, resumeToken, options = {}) => {
    var _a;
    const body = {
      site_key: siteKey,
      public_key: publicKey,
      resume_token: resumeToken,
      action: (_a = options.action) != null ? _a : "identify"
    };
    if (options.conversationId !== void 0) {
      body.conversation_id = options.conversationId;
    }
    if (options.replaceCurrent !== void 0) {
      body.replace_current = options.replaceCurrent;
    }
    try {
      const response = await fetch(`${widgetOrigin}/api/public/widget-bootstrap`, {
        method: "POST",
        headers: { "Content-Type": "text/plain;charset=UTF-8" },
        body: JSON.stringify(body)
      });
      if (!response.ok) {
        return null;
      }
      return parseBootstrapResult(await response.json());
    } catch (e) {
      return null;
    }
  };

  // embed-loader/sanitize.ts
  var MAX_URL = 2048;
  var MAX_TITLE = 200;
  var originFromHref = (href) => {
    try {
      const url = new URL(href);
      if (url.protocol !== "http:" && url.protocol !== "https:") {
        return "";
      }
      return url.origin;
    } catch (e) {
      return "";
    }
  };
  var sanitizePageUrl = (raw) => {
    const clipped = raw.length > MAX_URL ? raw.slice(0, MAX_URL) : raw;
    try {
      const url = new URL(clipped);
      if (url.protocol !== "http:" && url.protocol !== "https:") {
        return "";
      }
      return `${url.origin}${url.pathname}`;
    } catch (e) {
      return "";
    }
  };
  var sanitizeTitle = (raw) => raw.slice(0, MAX_TITLE);
  var originFromScript = (script2) => {
    if (script2 === null || script2.src === "") {
      return "";
    }
    return originFromHref(script2.src);
  };

  // embed-loader/iframe.ts
  var PANEL_STYLE = [
    "[data-supportchat-panel]{transform-origin:bottom right;transition:opacity 220ms ease,transform 300ms cubic-bezier(0.22,1,0.36,1),border-radius 300ms cubic-bezier(0.22,1,0.36,1);will-change:transform,opacity}",
    "@media (prefers-reduced-motion: reduce){[data-supportchat-panel]{transition:none}}"
  ].join("");
  var ensurePanelStyle = (doc) => {
    if (doc.querySelector("[data-supportchat-panel-style]") !== null) {
      return;
    }
    const style = doc.createElement("style");
    style.setAttribute("data-supportchat-panel-style", "");
    style.textContent = PANEL_STYLE;
    doc.head.appendChild(style);
  };
  var createPanel = (doc, widgetOrigin, siteKey, publicKey, parentOrigin) => {
    ensurePanelStyle(doc);
    const iframe = doc.createElement("iframe");
    iframe.title = "SupportChat";
    const widgetUrl = new URL("/widget", widgetOrigin);
    widgetUrl.searchParams.set("site_key", siteKey);
    widgetUrl.searchParams.set("public_key", publicKey);
    widgetUrl.searchParams.set("parent_origin", parentOrigin);
    iframe.src = widgetUrl.toString();
    iframe.setAttribute("data-supportchat-panel", "");
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
      "pointer-events:none"
    ].join(";");
    iframe.hidden = true;
    doc.body.appendChild(iframe);
    return iframe;
  };
  var postToWidget = (state, frame) => {
    const iframe = state.iframe;
    if (iframe === null || !iframe.isConnected) {
      return;
    }
    const target = iframe.contentWindow;
    if (target === null || target === void 0) {
      return;
    }
    try {
      target.postMessage(frame, state.widgetOrigin);
    } catch (e) {
      return;
    }
  };
  var pageContext = (win, doc) => {
    try {
      return {
        page_url: sanitizePageUrl(win.location.href),
        page_title: sanitizeTitle(doc.title),
        referrer: sanitizePageUrl(doc.referrer)
      };
    } catch (e) {
      return { page_url: "", page_title: "", referrer: "" };
    }
  };
  var sendBootstrap = (state, win, doc) => {
    if (state.bootstrap === null) {
      return;
    }
    if (state.bootstrap.type === "host.bootstrap") {
      postToWidget(state, { ...state.bootstrap, ...pageContext(win, doc) });
      return;
    }
    postToWidget(state, state.bootstrap);
  };
  var sendContext = (state, win, doc) => {
    if (state.bootstrap === null) {
      return;
    }
    postToWidget(state, { type: "host.context", ...pageContext(win, doc) });
  };
  var acceptWidgetFrame = (state, event, handlers) => {
    if (event.origin !== state.widgetOrigin) {
      return;
    }
    if (state.iframe === null || event.source !== state.iframe.contentWindow) {
      return;
    }
    const frame = parseWidgetToHost(event.data);
    if (frame === null) {
      return;
    }
    dispatchWidgetFrame(state, frame, handlers);
  };
  var dispatchWidgetFrame = (state, frame, handlers) => {
    switch (frame.type) {
      case "widget.ready":
        handlers.onReady();
        return;
      case "widget.painted":
        handlers.onPainted();
        return;
      case "widget.activated":
        handlers.onActivated();
        return;
      case "widget.rebootstrap":
        handlers.onRebootstrap(frame.conversation_id);
        return;
      case "widget.close":
        handlers.onClose();
        return;
      case "widget.show_history":
        handlers.onShowHistory();
        return;
      case "widget.open_conversation":
        handlers.onOpenConversation(frame.conversation_id, frame.replace_current);
        return;
      case "widget.reset_current":
        handlers.onResetCurrent();
        return;
      case "widget.delete_all":
        handlers.onDeleteAll();
        return;
      case "widget.open_url":
        handlers.onOpenUrl(frame.url);
        return;
      case "widget.resize":
        applyWidgetResize(state, frame);
        return;
      default:
        return;
    }
  };
  var prefersReducedMotion = (iframe) => {
    var _a, _b, _c;
    return (_c = (_b = (_a = iframe.ownerDocument.defaultView) == null ? void 0 : _a.matchMedia) == null ? void 0 : _b.call(_a, "(prefers-reduced-motion: reduce)").matches) != null ? _c : false;
  };
  var resetWidgetTransform = (iframe) => {
    iframe.style.transform = "translateY(0) scale(1)";
  };
  var animateWidgetResize = (iframe, currentWidth, currentHeight, targetWidth, targetHeight) => {
    iframe.style.transition = "none";
    iframe.style.transform = `translateY(0) scale(${currentWidth / targetWidth}, ${currentHeight / targetHeight})`;
    iframe.getBoundingClientRect();
    const startTransition = () => {
      iframe.style.transition = "";
      resetWidgetTransform(iframe);
    };
    const widgetWindow = iframe.ownerDocument.defaultView;
    if (widgetWindow == null ? void 0 : widgetWindow.requestAnimationFrame) {
      widgetWindow.requestAnimationFrame(startTransition);
      return;
    }
    startTransition();
  };
  var applyWidgetResize = (state, frame) => {
    var _a;
    if (state.iframe === null) {
      return;
    }
    const iframe = state.iframe;
    const targetWidth = (_a = frame.width) != null ? _a : Number.parseFloat(iframe.style.width);
    const targetHeight = frame.height;
    const bounds = iframe.getBoundingClientRect();
    const currentWidth = bounds.width || Number.parseFloat(iframe.style.width);
    const currentHeight = bounds.height || Number.parseFloat(iframe.style.height);
    iframe.style.height = `${targetHeight}px`;
    iframe.style.width = `${targetWidth}px`;
    if (prefersReducedMotion(iframe) || currentWidth === 0 || currentHeight === 0) {
      resetWidgetTransform(iframe);
      return;
    }
    animateWidgetResize(iframe, currentWidth, currentHeight, targetWidth, targetHeight);
  };

  // embed-loader/launcher.ts
  var INK = "#0D1F3A";
  var PAPER = "#FFFFFF";
  var STEEL = "#2456A0";
  var mountLauncher = (doc, handleOpen2, widgetOrigin) => {
    const style = doc.createElement("style");
    style.textContent = "[data-supportchat-launcher]{transition:transform 180ms ease,box-shadow 180ms ease}[data-supportchat-launcher]:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(11,35,71,0.28)}[data-supportchat-launcher]:active{transform:translateY(0) scale(.96)}[data-supportchat-launcher]:focus-visible{outline:2px solid #2456A0;outline-offset:2px}@media (prefers-reduced-motion: reduce){[data-supportchat-launcher]{transition:none}}";
    doc.head.appendChild(style);
    const button = doc.createElement("button");
    button.type = "button";
    button.setAttribute("aria-label", "Open chat");
    button.setAttribute("data-supportchat-launcher", "");
    button.style.cssText = [
      "position:fixed",
      "right:24px",
      "bottom:24px",
      "width:56px",
      "height:56px",
      "padding:0",
      "border:0",
      "border-radius:50%",
      "background:#0B0B0B",
      "cursor:pointer",
      "z-index:2147483646",
      "touch-action:manipulation",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "overflow:hidden",
      "box-shadow:0 8px 24px rgba(11,35,71,0.28)"
    ].join(";");
    const icon = doc.createElement("span");
    icon.textContent = "Chat"

    icon.setAttribute("aria-hidden", "true");


    icon.style.cssText = "color:white;font:600 12px/1 system-ui,sans-serif";
    button.appendChild(icon);
    button.addEventListener("click", handleOpen2);
    doc.body.appendChild(button);
    return button;
  };
  var showHostError = (doc, handleRetry) => {
    const existing = doc.querySelector("[data-supportchat-error]");
    if (existing instanceof HTMLElement) {
      existing.hidden = false;
      return existing;
    }
    const panel = doc.createElement("div");
    panel.setAttribute("data-supportchat-error", "");
    panel.setAttribute("role", "alert");
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
      "font:14px/1.4 system-ui,sans-serif"
    ].join(";");
    const message = doc.createElement("p");
    message.textContent = "Chat is not available on this page";
    const retry = doc.createElement("button");
    retry.type = "button";
    retry.setAttribute("aria-label", "Retry");
    retry.textContent = "Retry";
    retry.style.cssText = `margin-top:12px;background:${STEEL};color:${PAPER};border:0;border-radius:8px;padding:8px 12px;cursor:pointer`;
    retry.addEventListener("click", handleRetry);
    panel.append(message, retry);
    doc.body.appendChild(panel);
    return panel;
  };
  var hideHostError = (doc) => {
    const existing = doc.querySelector("[data-supportchat-error]");
    if (existing instanceof HTMLElement) {
      existing.hidden = true;
    }
  };

  // embed-loader/navigation.ts
  var NAVIGATE_MS = 300;
  var watchNavigation = (win, notify) => {
    let timer = 0;
    const debounced = () => {
      win.clearTimeout(timer);
      timer = win.setTimeout(notify, NAVIGATE_MS);
    };
    const history = win.history;
    const push = history.pushState.bind(history);
    const replace = history.replaceState.bind(history);
    history.pushState = ((data, unused, url) => {
      const result = push(data, unused, url);
      debounced();
      return result;
    });
    history.replaceState = ((data, unused, url) => {
      const result = replace(data, unused, url);
      debounced();
      return result;
    });
    win.addEventListener("popstate", debounced);
    const navigation = win.navigation;
    if (navigation !== void 0) {
      navigation.addEventListener("navigate", debounced);
    }
  };

  // embed-loader/storage.ts
  var visitorStorageKey = (siteKey) => `supportchat.visitor.${siteKey}`;
  var readResumeToken = (siteKey) => {
    try {
      return window.localStorage.getItem(visitorStorageKey(siteKey));
    } catch (e) {
      return null;
    }
  };
  var writeResumeToken = (siteKey, token) => {
    try {
      window.localStorage.setItem(visitorStorageKey(siteKey), token);
    } catch (e) {
      return;
    }
  };
  var clearResumeToken = (siteKey) => {
    try {
      window.localStorage.removeItem(visitorStorageKey(siteKey));
    } catch (e) {
      return;
    }
  };

  // embed-loader/install.ts
  var BOOTSTRAP_RETRY_COUNT = 5;
  var BOOTSTRAP_RETRY_MS = 100;
  var PANEL_MOTION_MS = 300;
  var reducedMotionDelay = (win) => {
    try {
      return win.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : PANEL_MOTION_MS;
    } catch (e) {
      return 0;
    }
  };
  var resumeFor = (runtime) => {
    var _a;
    return (_a = runtime.pendingResume) != null ? _a : readResumeToken(runtime.config.siteKey);
  };
  var clearRetryTimer = (runtime) => {
    if (runtime.retryTimer !== null) {
      clearTimeout(runtime.retryTimer);
      runtime.retryTimer = null;
    }
  };
  var clearHideTimer = (runtime) => {
    if (runtime.hideTimer !== null) {
      clearTimeout(runtime.hideTimer);
      runtime.hideTimer = null;
    }
  };
  var setLauncherBusy = (runtime, busy) => {
    runtime.launcher.setAttribute("aria-busy", busy ? "true" : "false");
  };
  var bootstrapFrame = (runtime) => {
    return runtime.bootstrap;
  };
  var panelState = (runtime) => {
    return {
      widgetOrigin: runtime.widgetOrigin,
      iframe: runtime.iframe,
      pendingResume: runtime.pendingResume,
      bootstrap: bootstrapFrame(runtime),
      launcher: runtime.launcher
    };
  };
  var sendCurrentBootstrap = (runtime) => {
    if (runtime.iframe === null || !runtime.iframe.isConnected) {
      return;
    }
    sendBootstrap(panelState(runtime), runtime.win, runtime.doc);
  };
  var sendBootstrapWithRetry = (runtime) => {
    clearRetryTimer(runtime);
    let attempt = 0;
    const tick = () => {
      runtime.retryTimer = null;
      if (runtime.bootstrapAcked || runtime.bootstrap === null || runtime.iframe === null || !runtime.iframe.isConnected) {
        return;
      }
      sendCurrentBootstrap(runtime);
      attempt += 1;
      if (attempt < BOOTSTRAP_RETRY_COUNT) {
        runtime.retryTimer = setTimeout(tick, BOOTSTRAP_RETRY_MS);
      }
    };
    tick();
  };
  var hidePanel = (runtime) => {
    clearHideTimer(runtime);
    setLauncherBusy(runtime, false);
    if (runtime.iframe !== null) {
      runtime.iframe.style.opacity = "0";
      runtime.iframe.style.transform = "translateY(16px) scale(0.96)";
      runtime.iframe.style.pointerEvents = "none";
      const delay = reducedMotionDelay(runtime.win);
      runtime.hideTimer = setTimeout(() => {
        runtime.hideTimer = null;
        if (runtime.iframe !== null && runtime.launcher.hidden === false) {
          runtime.iframe.hidden = true;
        }
      }, delay);
    }
    runtime.launcher.hidden = false;
    runtime.launcher.focus();
  };
  var showPanel = (runtime) => {
    clearHideTimer(runtime);
    setLauncherBusy(runtime, false);
    if (runtime.iframe !== null) {
      runtime.iframe.hidden = false;
      runtime.iframe.style.pointerEvents = "auto";
      runtime.win.requestAnimationFrame(() => {
        if (runtime.iframe === null) {
          return;
        }
        runtime.iframe.style.opacity = "1";
        runtime.iframe.style.transform = "translateY(0) scale(1)";
      });
    }
    runtime.launcher.hidden = true;
  };
  var persistResumeIfReady = (runtime) => {
    if (!runtime.visitorActivated || runtime.pendingResume === null) {
      return;
    }
    writeResumeToken(runtime.config.siteKey, runtime.pendingResume);
  };
  var persistActivated = (runtime) => {
    runtime.visitorActivated = true;
    runtime.bootstrapAcked = true;
    clearRetryTimer(runtime);
    persistResumeIfReady(runtime);
  };
  var warmPanel = (runtime) => {
    if (runtime.iframe !== null) {
      return;
    }
    runtime.iframe = createPanel(
      runtime.doc,
      runtime.widgetOrigin,
      runtime.config.siteKey,
      runtime.config.publicKey,
      originFromHref(runtime.win.location.href)
    );
  };
  var applyBootstrap = (runtime, result) => {
    if (result.mode === "conversation") {
      runtime.bootstrap = {
        type: "host.bootstrap",
        bootstrap_token: result.bootstrap_token,
        widget: result.widget,
        page_url: "",
        page_title: "",
        referrer: "",
        ...result.conversation === void 0 ? {} : { conversation: result.conversation }
      };
    } else if (result.mode === "identity") {
      runtime.bootstrap = { type: "host.identity", widget: result.widget, identity: result.identity };
    } else {
      runtime.bootstrap = {
        type: "host.history",
        widget: result.widget,
        identity: result.identity,
        conversations: result.conversations
      };
    }
    runtime.bootstrapAcked = false;
    if (result.mode === "conversation" && result.resume_token !== void 0) {
      runtime.pendingResume = result.resume_token;
    }
    warmPanel(runtime);
    hideHostError(runtime.doc);
    persistResumeIfReady(runtime);
  };
  var handleHostMessage = (runtime, event) => {
    acceptWidgetFrame(panelState(runtime), event, {
      onReady: () => sendBootstrapWithRetry(runtime),
      onPainted: () => {
        runtime.panelPainted = true;
        showPanel(runtime);
      },
      onActivated: () => persistActivated(runtime),
      onRebootstrap: (conversationId) => {
        void runBootstrap(runtime, {
          action: conversationId ? "refresh" : "identify",
          conversationId
        });
      },
      onClose: () => hidePanel(runtime),
      onShowHistory: () => void runBootstrap(runtime, { action: "history" }),
      onOpenConversation: (conversationId, replaceCurrent) => void runBootstrap(runtime, {
        action: "open",
        conversationId,
        replaceCurrent
      }),
      onResetCurrent: () => void runBootstrap(runtime, { action: "reset" }),
      onDeleteAll: () => void runBootstrap(runtime, { action: "forget" }),
      onOpenUrl: (url) => {
        runtime.win.open(url, "_blank", "noopener,noreferrer");
      }
    });
  };
  var runBootstrap = async (runtime, options = {}) => {
    if (runtime.opening) {
      return;
    }
    runtime.opening = true;
    const result = await requestBootstrap(
      runtime.widgetOrigin,
      runtime.config.siteKey,
      runtime.config.publicKey,
      resumeFor(runtime),
      options
    );
    runtime.opening = false;
    if (result === null) {
      setLauncherBusy(runtime, false);
      showHostError(runtime.doc, () => {
        void runBootstrap(runtime);
      });
      return;
    }
    if (result.mode === "forgotten") {
      clearResumeToken(runtime.config.siteKey);
      runtime.pendingResume = null;
      runtime.bootstrap = null;
      runtime.visitorActivated = false;
      void runBootstrap(runtime);
      return;
    }
    applyBootstrap(runtime, result);
    sendBootstrapWithRetry(runtime);
  };
  var handleOpen = (runtime) => {
    hideHostError(runtime.doc);
    if (runtime.iframe !== null && runtime.panelPainted) {
      showPanel(runtime);
      return;
    }
    setLauncherBusy(runtime, true);
    warmPanel(runtime);
    void runBootstrap(runtime);
  };
  var preconnectWidget = (doc, widgetOrigin) => {
    if (doc.querySelector(`link[rel="preconnect"][href="${widgetOrigin}"]`) !== null) {
      return;
    }
    const link = doc.createElement("link");
    link.rel = "preconnect";
    link.setAttribute("href", widgetOrigin);
    doc.head.appendChild(link);
  };
  var installSupportChat = (win, doc, script2) => {
    if (win.__supportchatInstalled === true) {
      return;
    }
    const widgetOrigin = originFromScript(script2);
    const config = win.__supportchat;
    if (widgetOrigin === "" || config === void 0 || config.siteKey === "" || config.publicKey === "") {
      console.error("SupportChat: widget configuration is missing");
      return;
    }
    win.__supportchatInstalled = true;
    preconnectWidget(doc, widgetOrigin);
    const runtime = {
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
      hideTimer: null
    };
    runtime.launcher = mountLauncher(doc, () => handleOpen(runtime), widgetOrigin);
    runtime.launcher.addEventListener("pointerenter", () => warmPanel(runtime));
    runtime.launcher.addEventListener("focus", () => warmPanel(runtime));
    win.addEventListener("message", (event) => handleHostMessage(runtime, event));
    watchNavigation(win, () => {
      sendContext(panelState(runtime), win, doc);
    });
  };

  // embed-loader/index.ts
  var script = document.currentScript;
  installSupportChat(window, document, script instanceof HTMLScriptElement ? script : null);
})();
