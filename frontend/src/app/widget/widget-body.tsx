"use client"

import { useCallback } from "react"

import type { PublicWidgetConfig } from "@/lib/postmessage"

import { ChatStatus } from "./chat-status"
import { Composer } from "./composer"
import { openUrlOnHost } from "./host-bridge"
import { PrechatForm, type PrechatFields } from "./prechat-form"
import { isCenteredNotice, isClosedNotice, Transcript } from "./transcript"
import type { ChatView } from "./visitor-session"

type WidgetBodyProps = {
  config: PublicWidgetConfig
  view: ChatView
  reconnecting: boolean
  sending: boolean
  privacyVisible: boolean
  onPrechat: (fields: PrechatFields) => void
  onRestart: () => void
  onSend: (body: string) => void
  onDismissPrivacy: () => void
}

const latestSystemReason = (lines: { role: string; system_reason?: string | null }[]) => {
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index]
    if (line.role === "system" && line.system_reason) {
      return line.system_reason
    }
  }
  return null
}

const transcriptNotice = (
  state: string,
  visitorClosed: boolean,
  hasClosedLine: boolean,
  lines: ChatView["lines"],
) => {
  if (visitorClosed) {
    return hasClosedLine ? undefined : "This chat is closed"
  }
  if (state === "human" && !lines.some(isCenteredNotice)) {
    return "A human has joined"
  }
  return undefined
}

const ClosedFooter = ({ onRestart }: { onRestart: () => void }) => (
  <div className="border-line bg-ice border-t px-5 py-4">
    <button
      type="button"
      onClick={onRestart}
      className="bg-ember hover:bg-ember-mid focus-visible:ring-steel dark:text-navy-deep min-h-11 cursor-pointer rounded-[8px] px-4 py-2 text-sm font-bold text-white transition-[background-color,transform] duration-150 ease-out focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
    >
      Start a new chat
    </button>
  </div>
)

const PrivacyBanner = ({
  privacyUrl,
  onDismiss,
}: {
  privacyUrl: string
  onDismiss: () => void
}) => {
  const handleOpenPrivacy = useCallback(() => {
    openUrlOnHost(privacyUrl)
  }, [privacyUrl])

  return (
    <div className="widget-enter border-line bg-paper mx-5 mb-3 flex items-start gap-3 rounded-[8px] border p-4 shadow-[0_8px_22px_rgba(13,31,58,0.08)]">
      <p className="text-mute min-w-0 flex-1 text-xs leading-5">
        By chatting here, you agree that we and authorized partners may process and monitor this
        conversation in line with our{" "}
        <button
          type="button"
          className="text-steel cursor-pointer font-bold"
          onClick={handleOpenPrivacy}
        >
          Privacy notice
        </button>
        .
      </p>
      <button
        type="button"
        aria-label="Dismiss privacy notice"
        onClick={onDismiss}
        className="text-mute hover:bg-ice text-ink focus-visible:ring-steel flex size-8 shrink-0 items-center justify-center rounded-full focus-visible:ring-2 focus-visible:outline-none"
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  )
}

const ActiveChat = ({
  config,
  view,
  reconnecting,
  sending,
  privacyVisible,
  state,
  onRestart,
  onSend,
  onDismissPrivacy,
}: WidgetBodyProps & { state: Exclude<ChatView["conversation"], null | "prechat"> }) => {
  const visitorClosed = state === "closed" || (state === "queued" && !config.human_enabled)
  const systemReason = latestSystemReason(view.lines)
  const hideComposer = visitorClosed || !config.bot_enabled || state === "queued"
  const hasClosedLine = view.lines.some(isClosedNotice)
  const notice = transcriptNotice(state, visitorClosed, hasClosedLine, view.lines)

  return (
    <>
      <ChatStatus
        reconnecting={reconnecting}
        systemReason={state === "queued" && !visitorClosed ? systemReason : null}
      />
      <Transcript
        lines={view.lines}
        typing={view.typing}
        autoFollow
        muted={visitorClosed}
        notice={notice}
        conversationState={state}
      />
      {visitorClosed ? (
        <ClosedFooter onRestart={onRestart} />
      ) : hideComposer ? null : (
        <>
          {privacyVisible ? (
            <PrivacyBanner privacyUrl={config.privacy_url} onDismiss={onDismissPrivacy} />
          ) : null}
          <Composer disabled={false} sending={sending} onSend={onSend} />
        </>
      )}
    </>
  )
}

export const WidgetBody = (props: WidgetBodyProps) => {
  const state = props.view.conversation
  if (state === null) {
    return <p className="text-mute p-4 text-sm">Connecting…</p>
  }
  if (state === "prechat") {
    return (
      <PrechatForm
        name={props.config.name}
        privacyUrl={props.config.privacy_url}
        onSubmit={props.onPrechat}
      />
    )
  }
  return <ActiveChat {...props} state={state} />
}
