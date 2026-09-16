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

const ClosedFooter = ({
  contactInfo,
  onRestart,
}: {
  contactInfo: string[]
  onRestart: () => void
}) => (
  <div className="bg-transparent px-3 pt-2 pb-3">
    <section className="widget-enter mb-3 rounded-[20px] bg-white/72 px-4 py-3.5 text-center shadow-[0_10px_24px_rgba(13,31,58,0.10)] backdrop-blur-xl">
      <h2 className="text-ink text-sm font-extrabold tracking-[-0.02em]">
        Thanks for chatting with us.
      </h2>
      <p className="text-mute mt-1 text-xs leading-5">
        Take care — we’ll be here when you need us.
      </p>
      {contactInfo.length ? (
        <div className="border-line/70 mt-3 border-t pt-3">
          <p className="text-ink text-[10px] font-extrabold tracking-[0.12em] uppercase">
            Contact us
          </p>
          <ul className="text-steel mt-1.5 space-y-0.5 text-xs font-bold">
            {contactInfo.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
    <button
      type="button"
      onClick={onRestart}
      className="bg-ember hover:bg-ember-mid focus-visible:ring-ember/30 min-h-11 w-full cursor-pointer rounded-[22px] px-4 py-2 text-sm font-bold text-white shadow-[0_10px_24px_rgba(196,85,22,0.22)] transition-[background-color,box-shadow,transform] duration-200 ease-out hover:-translate-y-px hover:shadow-[0_14px_28px_rgba(196,85,22,0.28)] focus-visible:ring-4 focus-visible:outline-none active:scale-[0.98]"
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
    <div className="widget-enter mx-3 mb-2 flex items-start gap-3 rounded-[20px] border border-white/80 bg-white/76 p-3.5 shadow-[0_10px_24px_rgba(13,31,58,0.10)] backdrop-blur-xl">
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
        className="text-mute text-ink focus-visible:ring-steel flex size-8 shrink-0 items-center justify-center rounded-full hover:bg-white focus-visible:ring-2 focus-visible:outline-none"
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
        <ClosedFooter contactInfo={config.contact_info} onRestart={onRestart} />
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
