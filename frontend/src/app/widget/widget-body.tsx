"use client"

import { useCallback } from "react"

import { Button } from "@/components/ui/button"
import { StateIcon } from "@/components/ui/state-icon"
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
  loadingOlder: boolean
  privacyVisible: boolean
  onPrechat: (fields: PrechatFields) => void
  onRestart: () => void
  onSend: (body: string) => boolean
  onWaitChoice: (promptId: number, choice: "wait" | "end") => void
  onLoadOlder: () => void
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
      <h2 className="text-ink heading text-sm">Thanks for chatting with us.</h2>
      <p className="text-mute mt-1 text-xs leading-5">
        Take care — we’ll be here when you need us.
      </p>
      {contactInfo.length ? (
        <div className="border-line/70 mt-3 border-t pt-3">
          <p className="text-ink text-[10px] font-semibold tracking-[0.2em] uppercase">
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
    <Button
      type="button"
      variant="secondary"
      size="lg"
      onClick={onRestart}
      className="border-steel/15 bg-ice-2 text-navy hover:!text-navy focus-visible:ring-steel/30 min-h-11 w-full border px-4 text-sm leading-none font-bold shadow-[0_8px_20px_rgba(36,86,160,0.12)] hover:!bg-[#e6eefc] focus-visible:ring-4"
    >
      Start a new chat
    </Button>
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
        <Button
          type="button"
          variant="link"
          className="text-steel cursor-pointer font-bold"
          onClick={handleOpenPrivacy}
        >
          Privacy notice
        </Button>
        .
      </p>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Dismiss privacy notice"
        onClick={onDismiss}
        className="text-mute text-ink focus-visible:ring-steel flex size-8 shrink-0 items-center justify-center rounded-full focus-visible:ring-2 focus-visible:outline-none"
      >
        <StateIcon name="x" />
      </Button>
    </div>
  )
}

const OlderMessagesButton = ({
  visible,
  loading,
  onLoad,
}: {
  visible: boolean
  loading: boolean
  onLoad: () => void
}) =>
  visible ? (
    <Button type="button" variant="ghost" size="sm" disabled={loading} onClick={onLoad}>
      {loading ? "Loading older messages…" : "Load older messages"}
    </Button>
  ) : null

const WaitChoices = ({
  view,
  available,
  sending,
  reconnecting,
  onChoice,
}: {
  view: ChatView
  available: boolean
  sending: boolean
  reconnecting: boolean
  onChoice: WidgetBodyProps["onWaitChoice"]
}) => {
  const promptId = view.waitPromptId
  const keepWaiting = useCallback(() => {
    if (promptId) onChoice(promptId, "wait")
  }, [promptId, onChoice])
  const endChat = useCallback(() => {
    if (promptId) onChoice(promptId, "end")
  }, [promptId, onChoice])
  if (!available || view.conversation !== "queued" || !promptId) return null
  const disabled = sending || reconnecting
  return (
    <section
      aria-label="Continue waiting for a specialist"
      className="border-line/70 mx-3 mb-3 rounded-2xl border bg-white/80 p-3"
    >
      <p className="text-mute mb-3 text-xs leading-5">
        Keep your place in the queue, or end this chat.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button className="min-h-11 flex-1" disabled={disabled} onClick={keepWaiting}>
          Keep waiting
        </Button>
        <Button
          variant="secondary"
          className="min-h-11 flex-1"
          disabled={disabled}
          onClick={endChat}
        >
          End chat
        </Button>
      </div>
    </section>
  )
}

const ActiveChat = ({
  config,
  view,
  reconnecting,
  sending,
  loadingOlder,
  privacyVisible,
  state,
  onRestart,
  onSend,
  onWaitChoice,
  onLoadOlder,
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
      <OlderMessagesButton visible={view.hasOlder} loading={loadingOlder} onLoad={onLoadOlder} />
      <Transcript
        lines={view.lines}
        typing={view.typing}
        autoFollow
        muted={visitorClosed}
        notice={notice}
        conversationState={state}
        agentName={view.assignedName}
        companyName={config.name}
      />
      <WaitChoices
        view={view}
        available={config.human_enabled}
        sending={sending}
        reconnecting={reconnecting}
        onChoice={onWaitChoice}
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
