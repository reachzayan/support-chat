"use strict";
(() => {
  // src/lib/message-tone.ts
  var MESSAGE_TONE_URL = "/sounds/message.wav";
  var createMessageTone = (source = MESSAGE_TONE_URL) => {
    let audio;
    const prepare = () => {
      try {
        if (!audio) {
          audio = new Audio(source);
          audio.preload = "auto";
          audio.load();
        }
      } catch (e) {
        audio = void 0;
      }
    };
    const play = async () => {
      try {
        prepare();
        if (!audio) return false;
        audio.currentTime = 0;
        await audio.play();
        return true;
      } catch (e) {
        return false;
      }
    };
    const stop = () => audio == null ? void 0 : audio.pause();
    return { prepare, play, stop };
  };

  // src/lib/system-notification.ts
  var notificationPermission = () => {
    var _a, _b;
    return (_b = (_a = globalThis.Notification) == null ? void 0 : _a.permission) != null ? _b : "unavailable";
  };
  var preferNativeSound = () => {
    const macChromium = /Macintosh|Mac OS X/.test(navigator.userAgent) && /(?:Chrome|Chromium|Edg|OPR)\//.test(navigator.userAgent);
    return notificationPermission() === "granted" && !macChromium;
  };
  var alertSequence = 0;
  var showSystemNotification = (title, body, tag, onOpen) => {
    try {
      if (notificationPermission() !== "granted") return false;
      const notification = new Notification(title, {
        body,
        tag: `${tag}-${Date.now()}-${++alertSequence}`,
        silent: false
      });
      notification.addEventListener("click", () => {
        notification.close();
        window.focus();
        onOpen == null ? void 0 : onOpen();
      });
      return true;
    } catch (e) {
      return false;
    }
  };

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
  var parseVisitorProfile = (value) => {
    if (!isRecord(value) || typeof value.name !== "string" || typeof value.email !== "string" || typeof value.phone !== "string")
      return void 0;
    return { name: value.name, email: value.email, phone: value.phone };
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
      messages: value.messages.filter(isRecord),
      has_older: value.has_older === true,
      visitor_profile: parseVisitorProfile(value.visitor_profile)
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
      is_current: value.is_current,
      preview: typeof value.preview === "string" ? value.preview.slice(0, 180) : null
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
  var parseLayout = (value) => typeof value.fullscreen === "boolean" ? { type: "host.layout", fullscreen: value.fullscreen } : null;
  var parseHostToWidget = (value) => {
    if (!isRecord(value) || typeof value.type !== "string") {
      return null;
    }
    if (value.type === "host.sound") {
      return typeof value.enabled === "boolean" ? { type: "host.sound", enabled: value.enabled } : null;
    }
    if (value.type === "host.layout") {
      return parseLayout(value);
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
    if (value.type === "widget.sound") {
      return typeof value.enabled === "boolean" ? { type: "widget.sound", enabled: value.enabled } : null;
    }
    if (value.type === "widget.message") {
      if (typeof value.conversation_id !== "string" || !UUID_PATTERN.test(value.conversation_id) || typeof value.message_id !== "number" || !Number.isSafeInteger(value.message_id) || value.message_id <= 0)
        return null;
      return {
        type: "widget.message",
        conversation_id: value.conversation_id,
        message_id: value.message_id
      };
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
  var SHEET_QUERY = "(max-width: 640px), (max-height: 500px) and (max-width: 932px)";
  var SHEET_STYLE = [
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
    "transform-origin:bottom center"
  ].join(";");
  var isSheetLayout = (win) => {
    try {
      return win.matchMedia(SHEET_QUERY).matches;
    } catch (e) {
      return false;
    }
  };
  var PLACEHOLDER_STYLE = [
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
    "@media (prefers-reduced-motion: reduce){[data-supportchat-placeholder] .c365-spin{animation:none;border-color:#C45516}}"
  ].join("");
  var PANEL_STYLE = [
    PLACEHOLDER_STYLE,
    `@media ${SHEET_QUERY}{[data-supportchat-panel]{${SHEET_STYLE}}}`,
    "[data-supportchat-panel]{transform-origin:bottom right;transition:opacity 220ms ease,transform 300ms cubic-bezier(0.22,1,0.36,1),border-radius 300ms cubic-bezier(0.22,1,0.36,1);will-change:transform,opacity}",
    "@media (prefers-reduced-motion: reduce){[data-supportchat-panel]{transition:none}}"
  ].join("");
  var SCROLL_LOCK_ATTR = "data-supportchat-scroll-lock";
  var setHostScrollLock = (doc, locked) => {
    const root = doc.documentElement;
    if (locked) {
      if (root.hasAttribute(SCROLL_LOCK_ATTR)) return;
      root.setAttribute(SCROLL_LOCK_ATTR, root.style.overflow);
      root.style.overflow = "hidden";
      return;
    }
    const previous = root.getAttribute(SCROLL_LOCK_ATTR);
    if (previous === null) return;
    root.removeAttribute(SCROLL_LOCK_ATTR);
    root.style.overflow = previous;
  };
  var syncSheetViewport = (win, iframe) => {
    if (iframe === null) return;
    const viewport = win.visualViewport;
    if (!isSheetLayout(win) || viewport === null || viewport === void 0) {
      iframe.style.removeProperty("--supportchat-vvh");
      iframe.style.removeProperty("--supportchat-vvt");
      return;
    }
    iframe.style.setProperty("--supportchat-vvh", `${Math.round(viewport.height)}px`);
    iframe.style.setProperty("--supportchat-vvt", `${Math.round(viewport.offsetTop)}px`);
  };
  var ensurePanelStyle = (doc) => {
    if (doc.querySelector("[data-supportchat-panel-style]") !== null) {
      return;
    }
    const style = doc.createElement("style");
    style.setAttribute("data-supportchat-panel-style", "");
    style.textContent = PANEL_STYLE;
    doc.head.appendChild(style);
  };
  var createPlaceholder = (doc) => {
    ensurePanelStyle(doc);
    const root = doc.createElement("div");
    root.setAttribute("data-supportchat-placeholder", "");
    root.setAttribute("role", "status");
    root.setAttribute("aria-live", "polite");
    root.setAttribute("aria-label", "Loading chat");
    root.hidden = true;
    const head = doc.createElement("div");
    head.className = "c365-head";
    const dot = doc.createElement("span");
    dot.className = "c365-dot";
    const line = doc.createElement("span");
    line.className = "c365-line";
    head.append(dot, line);
    const body = doc.createElement("div");
    body.className = "c365-body";
    const spin = doc.createElement("span");
    spin.className = "c365-spin";
    spin.setAttribute("aria-hidden", "true");
    const bar = doc.createElement("span");
    bar.className = "c365-bar";
    bar.setAttribute("aria-hidden", "true");
    body.append(spin, bar);
    root.append(head, body);
    doc.body.appendChild(root);
    return root;
  };
  var createPanel = (doc, widgetOrigin, siteKey, publicKey, parentOrigin) => {
    ensurePanelStyle(doc);
    const iframe = doc.createElement("iframe");
    iframe.title = "SupportChat";
    const widgetUrl = new URL("/widget", widgetOrigin);
    widgetUrl.searchParams.set("site_key", siteKey);
    widgetUrl.searchParams.set("public_key", publicKey);
    widgetUrl.searchParams.set("parent_origin", parentOrigin);
    const view = doc.defaultView;
    if (view !== null && isSheetLayout(view)) {
      widgetUrl.searchParams.set("layout", "sheet");
    }
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
    var _a, _b;
    switch (frame.type) {
      case "widget.message":
        (_a = handlers.onMessage) == null ? void 0 : _a.call(handlers, frame.conversation_id, frame.message_id);
        return;
      case "widget.sound":
        (_b = handlers.onSound) == null ? void 0 : _b.call(handlers, frame.enabled);
        return;
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
    style.textContent = '[data-supportchat-launcher]{transition:transform 180ms ease,box-shadow 180ms ease}[data-supportchat-launcher]:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(11,35,71,0.28)}[data-supportchat-launcher]:active{transform:translateY(0) scale(.96)}[data-supportchat-launcher]:focus-visible{outline:2px solid #2456A0;outline-offset:2px}[data-supportchat-launcher]{right:max(24px,env(safe-area-inset-right))!important;bottom:max(24px,env(safe-area-inset-bottom))!important}@media (max-width: 640px){[data-supportchat-launcher]{right:max(16px,env(safe-area-inset-right))!important;bottom:max(16px,env(safe-area-inset-bottom))!important}}[data-supportchat-launcher][aria-busy=true]::after{content:"";position:absolute;inset:-4px;border-radius:50%;border:3px solid rgba(196,85,22,.25);border-top-color:#C45516;animation:chat365-spin .8s linear infinite;pointer-events:none}@keyframes chat365-spin{to{transform:rotate(360deg)}}@media (prefers-reduced-motion: reduce){[data-supportchat-launcher]{transition:none}[data-supportchat-launcher][aria-busy=true]::after{animation:none;border-color:#C45516}}';
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
      "background:#0B2347",
      "cursor:pointer",
      "z-index:2147483646",
      "touch-action:manipulation",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "overflow:visible",
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
  var setLauncherUnread = (button, count) => {
    let badge = button.querySelector("[data-supportchat-unread]");
    if (!badge) {
      badge = button.ownerDocument.createElement("span");
      badge.setAttribute("data-supportchat-unread", "");
      badge.setAttribute("aria-hidden", "true");
      badge.style.cssText = "position:absolute;top:-3px;right:-3px;min-width:22px;height:22px;padding:0 5px;box-sizing:border-box;border-radius:999px;background:#C45516;color:#fff;border:2px solid #fff;font:bold 11px/18px system-ui,sans-serif;text-align:center;font-variant-numeric:tabular-nums;pointer-events:none";
      button.appendChild(badge);
    }
    badge.style.display = count > 0 ? "block" : "none";
    badge.textContent = count > 0 ? count > 99 ? "99+" : String(count) : "";
    button.setAttribute(
      "aria-label",
      count > 0 ? `Open chat, ${count} unread ${count === 1 ? "message" : "messages"}` : "Open chat"
    );
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
  var PLACEHOLDER_TIMEOUT_MS = 2e4;
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
  var hidePlaceholder = (runtime) => {
    if (runtime.placeholderTimer !== null) {
      clearTimeout(runtime.placeholderTimer);
      runtime.placeholderTimer = null;
    }
    if (runtime.placeholder !== null) {
      runtime.placeholder.hidden = true;
    }
  };
  var showPlaceholder = (runtime) => {
    if (runtime.placeholder === null) {
      runtime.placeholder = createPlaceholder(runtime.doc);
    }
    hidePlaceholder(runtime);
    runtime.placeholder.hidden = false;
    setHostScrollLock(runtime.doc, isSheetLayout(runtime.win));
    runtime.placeholderTimer = setTimeout(() => abortPlaceholder(runtime), PLACEHOLDER_TIMEOUT_MS);
  };
  var abortPlaceholder = (runtime) => {
    hidePlaceholder(runtime);
    setHostScrollLock(runtime.doc, false);
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
  var sendLayout = (runtime) => {
    postToWidget(panelState(runtime), {
      type: "host.layout",
      fullscreen: isSheetLayout(runtime.win)
    });
  };
  var hidePanel = (runtime) => {
    clearHideTimer(runtime);
    setHostScrollLock(runtime.doc, false);
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
    runtime.unread = 0;
    setLauncherUnread(runtime.launcher, 0);
    clearHideTimer(runtime);
    setLauncherBusy(runtime, false);
    setHostScrollLock(runtime.doc, isSheetLayout(runtime.win));
    hidePlaceholder(runtime);
    if (runtime.iframe !== null) {
      syncSheetViewport(runtime.win, runtime.iframe);
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
      onReady: () => {
        postToWidget(panelState(runtime), { type: "host.sound", enabled: runtime.soundEnabled });
        sendLayout(runtime);
        sendBootstrapWithRetry(runtime);
      },
      onMessage: (_chatId, messageId) => {
        if (messageId <= runtime.lastMessageId) return;
        runtime.lastMessageId = messageId;
        if (!runtime.panelPainted || runtime.launcher.hidden) return;
        runtime.unread += 1;
        setLauncherUnread(runtime.launcher, runtime.unread);
        if (runtime.soundEnabled) {
          const native = preferNativeSound() && showSystemNotification(
            "New chat message",
            "Open chat to read your reply.",
            `supportchat-widget-${runtime.config.siteKey}`,
            () => showPanel(runtime)
          );
          if (!native) void runtime.tone.play();
        }
      },
      onSound: (enabled) => {
        runtime.soundEnabled = enabled;
        if (!enabled) runtime.tone.stop();
        try {
          runtime.win.localStorage.setItem(`supportchat.sound.${runtime.config.siteKey}`, String(enabled));
        } catch (e) {
        }
        postToWidget(panelState(runtime), { type: "host.sound", enabled });
      },
      onPainted: () => {
        runtime.panelPainted = true;
        postToWidget(panelState(runtime), { type: "host.sound", enabled: runtime.soundEnabled });
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
      abortPlaceholder(runtime);
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
    if (runtime.soundEnabled) runtime.tone.prepare();
    hideHostError(runtime.doc);
    if (runtime.iframe !== null && runtime.panelPainted) {
      showPanel(runtime);
      return;
    }
    setLauncherBusy(runtime, true);
    showPlaceholder(runtime);
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
  var watchSheetLayout = (runtime) => {
    const { win } = runtime;
    const relayout = () => {
      syncSheetViewport(win, runtime.iframe);
      if (runtime.iframe !== null && !runtime.iframe.hidden) {
        setHostScrollLock(runtime.doc, isSheetLayout(win));
      }
      sendLayout(runtime);
    };
    try {
      win.matchMedia(SHEET_QUERY).addEventListener("change", relayout);
    } catch (e) {
    }
    const viewport = win.visualViewport;
    if (viewport !== null && viewport !== void 0) {
      const follow = () => syncSheetViewport(win, runtime.iframe);
      viewport.addEventListener("resize", follow);
      viewport.addEventListener("scroll", follow);
    }
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
    let soundEnabled = true;
    try {
      soundEnabled = win.localStorage.getItem(`supportchat.sound.${config.siteKey}`) !== "false";
    } catch (e) {
    }
    const runtime = {
      unread: 0,
      lastMessageId: 0,
      soundEnabled,
      tone: createMessageTone(new URL(MESSAGE_TONE_URL, widgetOrigin).href),
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
      placeholder: null,
      placeholderTimer: null
    };
    runtime.launcher = mountLauncher(doc, () => handleOpen(runtime), widgetOrigin);
    runtime.launcher.addEventListener("pointerenter", () => warmPanel(runtime));
    runtime.launcher.addEventListener("focus", () => warmPanel(runtime));
    win.addEventListener("message", (event) => handleHostMessage(runtime, event));
    watchSheetLayout(runtime);
    watchNavigation(win, () => {
      sendContext(panelState(runtime), win, doc);
    });
  };

  // embed-loader/index.ts
  var script = document.currentScript;
  installSupportChat(window, document, script instanceof HTMLScriptElement ? script : null);
})();
