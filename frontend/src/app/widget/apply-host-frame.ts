import type { HostToWidget, PublicWidgetConfig } from "@/lib/postmessage"

export const applyHostFrame = (
  frame: HostToWidget,
  origin: string,
  knownParent: string,
  setParentOrigin: (origin: string) => void,
  setConfig: (config: PublicWidgetConfig) => void,
  setPage: (page: { page_url: string; page_title: string; referrer: string }) => void,
) => {
  if (frame.type === "host.bootstrap") {
    setParentOrigin(origin)
    setConfig(frame.widget)
    setPage({ page_url: frame.page_url, page_title: frame.page_title, referrer: frame.referrer })
    return
  }
  if (knownParent === "" || origin !== knownParent) {
    return
  }
  setPage({ page_url: frame.page_url, page_title: frame.page_title, referrer: frame.referrer })
}
