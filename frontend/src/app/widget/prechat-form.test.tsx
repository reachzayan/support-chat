import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { PrechatForm } from "./prechat-form"

const PRIVACY =
  "Replies may be AI-generated and incorrect. Do not share Social Security, driver's-license or medical information."

describe("pre-chat form", () => {
  test("invalid email keeps the form visible, focuses Email, and sends nothing", async () => {
    const user = userEvent.setup()
    const handleSubmit = vi.fn()

    renderWithProviders(
      <PrechatForm
        name="SampleSite"
        privacyUrl="http://localhost:3000/privacy"
        onSubmit={handleSubmit}
      />,
    )

    await user.type(screen.getByLabelText("Full name"), "Ada Lopez")
    await user.type(screen.getByLabelText("Email"), "not-an-email")
    await user.click(screen.getByRole("button", { name: "Start the chat" }))

    expect(screen.getByRole("button", { name: "Start the chat" })).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toHaveFocus()
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true")
    expect(handleSubmit).not.toHaveBeenCalled()
  })

  test("empty required fields show inline errors", async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <PrechatForm
        name="SampleSite"
        privacyUrl="http://localhost:3000/privacy"
        onSubmit={vi.fn()}
      />,
    )

    await user.click(screen.getByRole("button", { name: "Start the chat" }))

    expect(screen.getByText("Full name is required.")).toBeInTheDocument()
    expect(screen.getByText("Email is required.")).toBeInTheDocument()
    expect(screen.getByLabelText("Full name")).toHaveAttribute("aria-invalid", "true")
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true")
  })

  test("shows assistant warning, privacy link, and inquiry label", () => {
    const handleSubmit = vi.fn()
    renderWithProviders(
      <PrechatForm
        name="SampleSite"
        privacyUrl="http://localhost:3000/privacy"
        onSubmit={handleSubmit}
      />,
    )

    expect(screen.getByText(PRIVACY)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Privacy notice" })).toBeInTheDocument()
    expect(screen.getByLabelText("Inquiry type")).toBeInTheDocument()
  })

  test("shows available inquiry choices when the field is opened", async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <PrechatForm
        name="SampleSite"
        privacyUrl="http://localhost:3000/privacy"
        onSubmit={vi.fn()}
      />,
    )

    await user.click(screen.getByLabelText("Inquiry type"))

    expect(await screen.findByRole("option", { name: "Results timing" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Applicant portal" })).toBeInTheDocument()
  })

  test("omits a demo name from the pre-chat heading", () => {
    renderWithProviders(
      <PrechatForm name="Demo" privacyUrl="http://localhost:3000/privacy" onSubmit={vi.fn()} />,
    )

    expect(screen.queryByRole("heading", { name: "Demo" })).not.toBeInTheDocument()
  })
})

describe("prechat layout", () => {
  test("error messages overlay the gap so field spacing stays uniform", async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <PrechatForm name="Support" privacyUrl="http://localhost:3000/privacy" onSubmit={vi.fn()} />,
    )
    await user.click(screen.getByRole("button", { name: "Start the chat" }))
    const error = document.getElementById("name-error")
    expect(error?.className).toContain("absolute")
    expect(document.getElementById("phone-error")?.className).toContain("absolute")
  })
})
