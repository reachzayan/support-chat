import { installSupportChat } from "./install"

const script = document.currentScript
installSupportChat(window, document, script instanceof HTMLScriptElement ? script : null)
