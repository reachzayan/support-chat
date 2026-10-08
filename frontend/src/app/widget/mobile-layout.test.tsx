import { screen } from "@testing-library/react"
import { describe, expect, test, vi } from "vitest"

import { parseHostToWidget } from "@/lib/postmessage"
import { renderWithProviders } from "@/test/render"

import { PrechatForm } from "./prechat-form"
import { WidgetLoading, WidgetShell } from "./widget-shell"

const shell = (fullscreen: boolean) =>
  renderWithProviders(
    <WidgetShell
      name="SupportChat"
      fullscreen={fullscreen}
      onClose={vi.fn()}
      onResetCurrent={vi.fn()}
      onDeleteAll={vi.fn()}
      onResize={vi.fn()}
    >
      <p>content</p>
    </WidgetShell>,
  )

describe("widget on phones", () => {
  test("full-screen shell hides the expand control and drops the card chrome", () => {
    shell(true)
    expect(screen.queryByRole("button", { name: "Expand chat" })).not.toBeInTheDocument()
    const dialog = screen.getByRole("dialog")
    expect(dialog).toHaveAttribute("data-layout", "sheet")
    expect(dialog).toHaveClass("rounded-none", "h-dvh")
    expect(dialog.className).toContain("env(safe-area-inset-bottom)")
  })

  test("floating panel keeps the expand control and rounded card", () => {
    shell(false)
    expect(screen.getByRole("button", { name: "Expand chat" })).toBeInTheDocument()
    expect(screen.getByRole("dialog")).toHaveAttribute("data-layout", "panel")
  })

  test("header buttons are at least 44px", () => {
    shell(false)
    for (const name of ["Expand chat", "More options", "Close chat"]) {
      expect(screen.getByRole("button", { name })).toHaveClass("size-11")
    }
  })

  test("loading state is announced and branded", () => {
    renderWithProviders(<WidgetLoading fullscreen />)
    expect(screen.getByLabelText("Loading chat")).toHaveClass("h-dvh")
  })

  test("host.layout frames parse", () => {
    expect(parseHostToWidget({ type: "host.layout", fullscreen: true })).toEqual({
      type: "host.layout",
      fullscreen: true,
    })
    expect(parseHostToWidget({ type: "host.layout", fullscreen: "yes" })).toBeNull()
  })
})

const renderForm = () =>
  renderWithProviders(
    <PrechatForm name="SupportChat" privacyUrl="http://x.test/p" onSubmit={vi.fn()} />,
  )

describe("pre-chat form on phones", () => {
  test("primary call to action uses the brand orange with a 44px+ target", () => {
    renderForm()
    const cta = screen.getByRole("button", { name: "Start the chat" })
    expect(cta).toHaveClass("bg-ember", "text-white", "min-h-12")
    expect(cta).not.toHaveClass("bg-ice-2")
  })

  test("fields carry mobile keyboard hints and 16px text", () => {
    renderForm()
    expect(screen.getByLabelText("Full name")).toHaveAttribute("autocomplete", "name")
    expect(screen.getByLabelText("Email")).toHaveAttribute("inputmode", "email")
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email")
    expect(screen.getByLabelText("Phone")).toHaveAttribute("inputmode", "tel")
    expect(screen.getByLabelText("Phone")).toHaveAttribute("type", "tel")
    for (const label of ["Full name", "Email", "Phone", "Message"]) {
      expect(screen.getByLabelText(label)).toHaveClass("text-base!")
    }
  })
})
