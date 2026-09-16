export const PUBLIC_KEY = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
export const SNIPPET = `<script>
  window.__supportchat = { siteKey: "samplesite", publicKey: "${PUBLIC_KEY}" };
</script>
<script async src="http://widget.localhost:3000/supportchat.js"></script>`

export const SITE = {
  id: "11111111-1111-4111-8111-111111111111",
  key: "samplesite",
  name: "SampleSite Support",
  greeting: "Talk to a specialist about screening.",
  privacy_url: "https://sample-site.example.com/privacy",
  public_key: PUBLIC_KEY,
  origins: ["https://missing.example"],
  snippet: SNIPPET,
  origins_missing_from_frame_ancestors: false,
  enabled: true,
  bot_enabled: true,
  human_enabled: true,
  callback_window_hours: 24,
  off_brand_blocklist: [],
  contact_info: [],
  website_url: "https://sample-site.example.com",
  widget_installed: null,
  widget_checked_at: null,
}

export const listPayload = {
  items: [SITE],
  frame_ancestors: ["http://localhost:3000"],
  widget_origin: "http://widget.localhost:3000",
}

export const mockListFetch = () => ({
  ok: true,
  status: 200,
  json: async () => listPayload,
})
