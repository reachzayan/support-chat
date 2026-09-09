export type ChatEmbedConfig = {
  siteKey: string
  publicKey: string
}

declare global {
  interface Window {
    __supportchat?: ChatEmbedConfig
  }
}
