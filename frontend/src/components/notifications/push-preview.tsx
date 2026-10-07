"use client"

import { MessageSquareIcon } from "lucide-react"
import { useCallback, useEffect, useId, useState } from "react"

import { staffRead } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { scenarios, type Scenario } from "./types"

type Content = { title: string; body: string; action_label: string }
const items = scenarios.map((scenario) => ({ value: scenario.id, label: scenario.label }))

export const usePushPreview = (siteId?: string) => {
  const [scenario, setScenario] = useState<Scenario>("needs_attention")
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ key: string; content: Content | null } | null>(null)
  const key = `${siteId}:${scenario}:${attempt}`
  useEffect(() => {
    if (!siteId) return
    let active = true
    const load = async () => {
      try {
        const query = new URLSearchParams({ site_id: siteId, scenario })
        const response = await staffRead(`/api/notifications/push/preview?${query}`)
        if (!response.ok) throw new Error("unavailable")
        const content: Content = await response.json()
        if (active) setResult({ key, content })
      } catch {
        if (active) setResult({ key, content: null })
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [siteId, scenario, key])
  const change = useCallback((value: Scenario | null) => {
    if (value) setScenario(value)
  }, [])
  const retry = useCallback(() => setAttempt((current) => current + 1), [])
  return {
    scenario,
    change,
    retry,
    content: result?.key === key ? result.content : null,
    loading: Boolean(siteId && result?.key !== key),
    error: result?.key === key && !result.content,
  }
}

export const PushPreview = ({ state }: { state: ReturnType<typeof usePushPreview> }) => {
  const id = useId()
  return (
    <div className="border-line mt-4 grid min-w-0 gap-3 border-t pt-4">
      <div className="grid gap-2 sm:max-w-sm">
        <label htmlFor={id} className="text-ink text-sm font-semibold">
          Preview activity
        </label>
        <Select value={state.scenario} onValueChange={state.change} items={items}>
          <SelectTrigger id={id} className="border-line bg-paper text-navy min-h-11 w-full px-3">
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start" alignItemWithTrigger={false}>
            {scenarios.map((scenario) => (
              <SelectItem key={scenario.id} value={scenario.id} className="min-h-11">
                {scenario.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {state.loading ? <output className="text-mute text-sm">Loading preview…</output> : null}
      {state.error ? (
        <div>
          <p role="alert" className="text-ember text-sm">
            Could not load the preview. Try again.
          </p>
          <Button variant="outline" className="mt-2 min-h-11" onClick={state.retry}>
            Retry preview
          </Button>
        </div>
      ) : null}
      {state.content ? (
        <figure
          aria-label="Notification preview"
          className="border-line bg-ice min-w-0 rounded-2xl border p-4"
        >
          <figcaption className="text-mute mb-3 flex items-center gap-2 text-xs">
            <MessageSquareIcon aria-hidden="true" className="text-steel size-4" />
            <span className="font-semibold">SupportChat</span>
            <span className="ml-auto">Example</span>
          </figcaption>
          <div aria-live="polite" className="grid min-w-0 gap-2">
            <p className="text-navy text-sm font-semibold break-words">{state.content.title}</p>
            <p className="text-ink text-sm break-words whitespace-pre-line">{state.content.body}</p>
            <p className="text-steel border-line mt-1 border-t pt-2 text-xs font-semibold">
              {state.content.action_label}
            </p>
          </div>
        </figure>
      ) : null}
      <p className="text-mute text-xs">
        Example for the selected website. Send it to check delivery; no chat or unread activity is
        created. Your device controls the final appearance.
      </p>
    </div>
  )
}
