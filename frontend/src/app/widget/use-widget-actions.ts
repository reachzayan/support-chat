"use client"

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
  const handleReset = useCallback(() => {
    socketRef.current?.close()
    socketRef.current = null
    postToParent({ type: "widget.reset" }, parentRef.current || guessParentOrigin())
  }, [parentRef, socketRef])
  const handleRestart = useCallback(() => {
    postToParent({ type: "widget.rebootstrap" }, parentRef.current)
  }, [parentRef])
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
      setSending(true)
      socketRef.current?.sendMessage(crypto.randomUUID(), body)
    },
    [setSending, socketRef],
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
    handleClose,
    handleReset,
    handleRestart,
    handlePrechat,
    handleSend,
    handleDismissPrivacy,
    handleResize,
  }
}
