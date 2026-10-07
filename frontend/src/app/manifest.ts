import type { MetadataRoute } from "next"

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SupportChat",
    short_name: "SupportChat",
    description: "Specialist chat for screening operations",
    start_url: "/admin/inbox",
    scope: "/",
    display: "standalone",
    background_color: "#F4F8FF",
    theme_color: "#0B2347",
    icons: [{ src: "/icon-watermark.png", sizes: "1060x1060", type: "image/png", purpose: "any" }],
  }
}
