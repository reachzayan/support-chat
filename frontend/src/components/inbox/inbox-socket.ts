import { agentSocketUrl, createAgentSocket } from "@/lib/agent-ws"
import { getAccessToken, redirectToLogin, refreshSession } from "@/lib/auth-client"
import type { createReconnectScheduler } from "@/lib/ws-reconnect"

import { applyAgentFrame, type InboxLive } from "./inbox-session"
import type { InboxFilter } from "./types"
import type { InboxRefs } from "./use-inbox-refs"

export type SocketApi = ReturnType<typeof createAgentSocket>

type AgentScheduler = ReturnType<typeof createReconnectScheduler>

export const bindAgentSocket = (
  refs: InboxRefs,
  setLive: (live: InboxLive) => void,
  reloadList: (filter: InboxFilter) => void,
  reloadDetail: (id: string) => void,
  scheduler: AgentScheduler,
) => {
  const socket = createAgentSocket({
    url: agentSocketUrl(),
    accessToken: getAccessToken() ?? "",
    onFrame: (frame) => {
      scheduler.markAuthenticated()
      const effect = applyAgentFrame(
        refs.liveRef.current,
        frame,
        refs.userRef.current,
        refs.selectedRef.current,
      )
      refs.liveRef.current = effect.live
      setLive(effect.live)
      if (effect.refetchList) {
        reloadList(refs.filterRef.current)
      }
      if (effect.refetchDetailId !== null) {
        reloadDetail(effect.refetchDetailId)
      }
    },
    onClose: (code) => {
      void handleAgentSocketClose(code, socket, refs, scheduler)
    },
  })
  return socket
}

export const resumeAgentSocket = (socket: SocketApi, refs: InboxRefs) => {
  socket.reconnect()
  if (refs.selectedRef.current !== null) {
    socket.subscribe(refs.selectedRef.current, refs.lastIdRef.current)
  }
  socket.flushUnacked()
}

const handleAgentSocketClose = async (
  code: number,
  socket: SocketApi,
  refs: InboxRefs,
  scheduler: AgentScheduler,
) => {
  if (code === 1000 || code === 4403) {
    return
  }
  if (code === 4401) {
    const result = await refreshSession()
    if (result.status === "unauthenticated") {
      redirectToLogin()
      return
    }
    if (result.status !== "authenticated") {
      return
    }
    socket.setAccessToken(getAccessToken() ?? "")
    scheduler.markAuthenticated()
    resumeAgentSocket(socket, refs)
    return
  }
  scheduler.handleClose()
}
