"use client"

/* oxlint-disable max-lines-per-function -- one hook owns the widget's outbound action contract */

import { useCallback, type RefObject } from "react"

import { guessParentOrigin, postToParent } from "./host-bridge"
import type { PrechatFields } from "./prechat-form"
import type { SocketApi } from "./use-visitor-connection"
import type { WidgetSize } from "./widget-shell"

export const useWidgetActions = (
  socketRef: RefObject<SocketApi | null>,
  parentRef: RefObject<string>,
  setSending: (sending: boolean) => void,
  setPrivacyVisible: (visible: boolean) => void,
) => {
  const handleClose = useCallback(() => {
    postToParent({ type: "widget.close" }, parentRef.current || guessParentOrigin())
  }, [parentRef])
  const handleResetCurrent = useCallback(() => {
    socketRef.current?.close()
    socketRef.current = null
    postToParent({ type: "widget.reset_current" }, parentRef.current || guessParentOrigin())
  }, [parentRef, socketRef])
  const handleDeleteAll = useCallback(() => {
    socketRef.current?.close()
    socketRef.current = null
    postToParent({ type: "widget.delete_all" }, parentRef.current || guessParentOrigin())
  }, [parentRef, socketRef])
  const handleRestart = handleResetCurrent
  const handleShowHistory = useCallback(() => {
    postToParent({ type: "widget.show_history" }, parentRef.current || guessParentOrigin())
  }, [parentRef])
  const handleOpenConversation = useCallback(
    (conversationId: string, replaceCurrent: boolean) => {
      socketRef.current?.close()
      socketRef.current = null
      postToParent(
        {
          type: "widget.open_conversation",
          conversation_id: conversationId,
          replace_current: replaceCurrent,
        },
        parentRef.current || guessParentOrigin(),
      )
    },
    [parentRef, socketRef],
  )
  const handlePrechat = useCallback(
    (fields: PrechatFields) => {
      socketRef.current?.sendPrechat({
        submission_id: crypto.randomUUID(),
        name: fields.name,
        email: fields.email,
        phone: fields.phone,
        inquiry_type: fields.inquiryType,
        message: fields.message,
      })
    },
    [socketRef],
  )
  const handleSend = useCallback(
    (body: string) => {
      if (socketRef.current === null) {
        return false
      }
      setSending(true)
      return socketRef.current.sendMessage(crypto.randomUUID(), body)
    },
    [setSending, socketRef],
  )
  const handleWaitChoice = useCallback(
    (promptId: number, choice: "wait" | "end") => {
      if (!socketRef.current) return
      setSending(true)
      socketRef.current.respondHandoffWait(promptId, choice)
    },
    [socketRef, setSending],
  )
  const handleDismissPrivacy = useCallback(() => setPrivacyVisible(false), [setPrivacyVisible])
  const handleResize = useCallback(
    (size: WidgetSize) => {
      postToParent(
        { type: "widget.resize", height: size.height, width: size.width },
        parentRef.current || guessParentOrigin(),
      )
    },
    [parentRef],
  )
  return {
    handleWaitChoice,
    handleClose,
    handleResetCurrent,
    handleDeleteAll,
    handleRestart,
    handleShowHistory,
    handleOpenConversation,
    handlePrechat,
    handleSend,
    handleDismissPrivacy,
    handleResize,
  }
}
